"""FastAPI app: health check, allowed-races listing, chat, and static plot
serving.

Run locally from the backend/ directory:
    uvicorn app.main:app --reload --port 8000

This is enough to run the backend standalone and, deployed, behind the real
frontend. See CLAUDE.md Phase 4 for the Dockerfile/deploy checklist.
"""
import os

from dotenv import load_dotenv

# Must run before importing agent, which reads GEMINI_API_KEY/GEMINI_MODEL
# from the environment at import time. Loads backend/.env for local dev;
# a no-op if the file doesn't exist (e.g. in production, where the real
# platform sets these as actual environment variables).
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from . import agent, races, tools

app = FastAPI(title="Pit Wall API")

# Comma-separated real origin(s) for the deployed frontend, e.g.
# "https://pitwall.vercel.app". Unset (the local-dev default) falls back to
# the Next.js dev server's own origins instead -- CLAUDE.md: "restricted to
# the deployed frontend origin (and localhost in dev)", which in practice
# means never both at once, since there's no reason a production API needs
# to accept requests claiming to come from localhost.
_allowed_origins_env = os.environ.get("ALLOWED_ORIGINS")
ALLOWED_ORIGINS = (
    [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
    if _allowed_origins_env
    else ["http://localhost:3000", "http://127.0.0.1:3000"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# get_remote_address reads request.client.host. Render (like most PaaS)
# terminates TLS and proxies the request, so uvicorn needs to run with
# --proxy-headers (see the Phase 4 Dockerfile/deploy notes) for this to see
# the visitor's real IP instead of the proxy's.
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    # slowapi's own default handler returns {"error": ...}; match the
    # {"detail": ...} shape every other error response here uses, since
    # that's what the frontend's error handling already expects (see
    # frontend/src/lib/api.ts: 429 -> ApiError("rate_limited", detail)).
    return JSONResponse(
        status_code=429,
        content={"detail": "You've sent a lot of messages in the last hour. Please try again later."},
    )


# tools.py creates PLOT_DIR on import (above), so it exists by the time this mounts.
app.mount("/plots", StaticFiles(directory=tools.PLOT_DIR), name="plots")


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=500)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/races")
def get_races():
    return {"races": races.list_races()}


@app.post("/api/chat")
@limiter.limit("20/hour")
def chat(request: Request, req: ChatRequest):
    try:
        reply, tool_calls, plots = agent.send_message(req.session_id, req.message)
    except agent.SessionLimitReached as e:
        raise HTTPException(status_code=400, detail=str(e))
    except agent.QuotaExceeded as e:
        raise HTTPException(status_code=503, detail=str(e))
    except agent.AgentNotConfigured as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"reply": reply, "plots": plots, "tool_calls": tool_calls}
