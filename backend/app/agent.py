"""Gemini chat agent: one chat session per session_id, wired to the tools in
tools.py, with per-request tool-call/plot capture and a friendly message when
Google's free-tier quota is hit.

Model name and API key are read from the environment only (GEMINI_MODEL,
GEMINI_API_KEY) -- see CLAUDE.md. Neither is hardcoded or defaulted here.
"""
import contextvars
import functools
import inspect
import os
import threading
import time

from google import genai
from google.genai import errors, types

from . import races, tools

MODEL = os.environ.get("GEMINI_MODEL")

SESSION_TTL_SECONDS = 30 * 60
MAX_SESSIONS = 200
MAX_MESSAGES_PER_SESSION = 30


class QuotaExceeded(Exception):
    """Google's free-tier quota (or, once Phase 3 adds it, our own daily cap) was hit."""


class SessionLimitReached(Exception):
    """This session has used its per-session message budget."""


class AgentNotConfigured(Exception):
    """GEMINI_MODEL isn't set, so no chat can be started."""


# ---- per-request recording --------------------------------------------
# Automatic function calling runs the tools deep inside chat.send_message(),
# so the only way to learn which tools ran and which plots they saved is to
# record it from inside the tools themselves. contextvars keep that recording
# isolated per request even though FastAPI serves concurrent requests from a
# threadpool: main.py's endpoint is a plain `def`, so it (and everything it
# calls, including these tools) runs inside one copied context per request.
_tool_calls_var = contextvars.ContextVar("tool_calls", default=None)
_plots_var = contextvars.ContextVar("plots", default=None)


def _recorder(fn):
    """Wrap a tool so every call is logged and any plot it saves is captured,
    without changing what Gemini sees. functools.wraps copies
    __name__/__doc__/__wrapped__, and inspect.signature() -- which is what the
    installed SDK actually uses to build the tool schema, confirmed by reading
    google.genai._automatic_function_calling_util.parse_function_declaration_json_schema
    -- follows __wrapped__ automatically. So the wrapped tool gets the same
    name, docstring and parameter schema as the bare function.
    """
    sig = inspect.signature(fn)

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        result = fn(*args, **kwargs)

        ok = not (isinstance(result, dict) and "error" in result)
        calls = _tool_calls_var.get()
        if calls is not None:
            calls.append({"name": fn.__name__, "args": dict(bound.arguments), "ok": ok})

        if ok and isinstance(result, dict) and result.get("plot_saved_to"):
            plots = _plots_var.get()
            if plots is not None:
                caption = f"{result.get('driver', '?')} stint {result.get('stint', '?')} ({result.get('compound', '?')})"
                plots.append({"url": f"/plots/{os.path.basename(result['plot_saved_to'])}", "caption": caption})

        return result

    return wrapper


TOOLS = [_recorder(tools.get_stints), _recorder(tools.fit_degradation), _recorder(tools.compare_drivers)]


def _system_instruction():
    races_line = "; ".join(f"{e['label']}" for e in races.list_races())
    return (
        "You are a Formula 1 race analyst. You answer questions about past races "
        "using ONLY the results of the tools you are given. Rules:\n"
        "- Use three-letter driver codes (VER, HAM, NOR...) when calling tools.\n"
        f"- This demo only has data for: {races_line}. If asked about any other race, "
        "say it isn't available in this demo instead of calling a tool.\n"
        "- If the year or race is missing from the question, ask for it before calling tools.\n"
        "- Never invent lap times, strategies or causes. If the tool data cannot support a claim, say so.\n"
        "- When you report degradation, mention the caveat returned by the tool, and mention every "
        'item in its "warnings" list if it is non-empty (for example a weak fit or a small sample).\n'
        "- If a plot was saved, mention that a plot is attached; do not recite the raw file path.\n"
        "- Keep answers short and concrete."
    )


# ---- Gemini client and chat sessions -----------------------------------
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client()  # reads GEMINI_API_KEY from the environment
    return _client


def _new_chat():
    if not MODEL:
        raise AgentNotConfigured("GEMINI_MODEL is not set on the server.")
    client = _get_client()
    return client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=_system_instruction(),
            tools=TOOLS,
            temperature=0.2,
        ),
    )


class _SessionEntry:
    __slots__ = ("chat", "last_used", "message_count")

    def __init__(self, chat):
        self.chat = chat
        self.last_used = time.monotonic()
        self.message_count = 0


_sessions = {}
_sessions_lock = threading.Lock()


def _sweep_expired_locked():
    now = time.monotonic()
    expired = [sid for sid, e in _sessions.items() if now - e.last_used > SESSION_TTL_SECONDS]
    for sid in expired:
        del _sessions[sid]


def _get_or_create_session(session_id):
    with _sessions_lock:
        _sweep_expired_locked()
        entry = _sessions.get(session_id)
        if entry is None:
            if len(_sessions) >= MAX_SESSIONS:
                oldest_sid = min(_sessions, key=lambda sid: _sessions[sid].last_used)
                del _sessions[oldest_sid]
            entry = _SessionEntry(_new_chat())
            _sessions[session_id] = entry
        return entry


def send_message(session_id, message):
    """Send one user message in session_id's chat.

    Returns (reply_text, tool_calls, plots). Raises SessionLimitReached,
    QuotaExceeded or AgentNotConfigured on the friendly-error paths.
    """
    entry = _get_or_create_session(session_id)
    if entry.message_count >= MAX_MESSAGES_PER_SESSION:
        raise SessionLimitReached(
            f"This conversation has reached its {MAX_MESSAGES_PER_SESSION}-message limit for this "
            "demo. Please start a new conversation."
        )

    calls_token = _tool_calls_var.set([])
    plots_token = _plots_var.set([])
    try:
        response = entry.chat.send_message(message)
        entry.last_used = time.monotonic()
        entry.message_count += 1
        return response.text, _tool_calls_var.get(), _plots_var.get()
    except errors.APIError as e:
        if e.code in (429, 503):
            raise QuotaExceeded(
                "The demo is busy right now (free API quota). Please try again in a bit, or tomorrow."
            ) from e
        raise
    finally:
        _tool_calls_var.reset(calls_token)
        _plots_var.reset(plots_token)
