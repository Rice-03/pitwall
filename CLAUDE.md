# Pit Wall: project brief for Claude Code

Read this whole file before writing any code. Work through the phases in order and stop at each checkpoint so I can review.

## 1. What we are building

Pit Wall is a public web app where a visitor asks Formula 1 race questions in plain English and an LLM answers by calling real analysis tools over FastF1 race data. The LLM does no maths. It picks tools, the tools compute, and the LLM explains the results. Plots render inline in the chat.

Example questions:
- "How many stops did VER make at Silverstone 2023, and on which tyres?"
- "Fit tyre degradation for HAM's second stint at Monza 2023."
- "Compare NOR and PIA's pace and strategy at Suzuka 2024."

Purpose: a portfolio piece I can show recruiters via a live link. It is a small, finished, honest project. It must look polished and work on the first click with no setup.

About me: final-year CS honours student, comfortable with Python, learning the web side. Explain non-obvious decisions in one or two sentences as you go. I am on Windows, so give commands that work in PowerShell and avoid bash-only scripts.

## 2. Existing prototype

`pitwall.py` in the repo root is a working single-file prototype: three tools plus a Gemini chat loop in the terminal. Treat it as the source of truth for tool behaviour.

Tools (keep signatures and docstrings, because the Gemini SDK builds the tool schema from them):
- `get_stints(year: int, race: str, driver: str) -> dict`
- `fit_degradation(year: int, race: str, driver: str, stint: int) -> dict` (OLS of lap time on tyre age, saves a PNG plot, returns raw and fuel-corrected slope plus a caveat string)
- `compare_drivers(year: int, race: str, driver_a: str, driver_b: str) -> dict`

Known facts about the prototype:
- It was only syntax-checked. It has never been run against real FastF1 data, so expect small bugs (column names, filters, dtype issues).
- The fuel-corrected slope uses an assumed constant (`FUEL_EFFECT_S_PER_LAP = 0.05`), because tyre age and fuel load cannot be separated within one stint. This is an approximation and the caveat must stay visible in answers.
- Model name is read from the `GEMINI_MODEL` env var. The API key comes from `GEMINI_API_KEY`. Never hardcode either.

## 3. Architecture

- **Frontend:** Next.js (App Router) with TypeScript and Tailwind. Deployed on Vercel.
- **Backend:** FastAPI (Python). Wraps the tools and the Gemini chat loop. Serves plot images. Holds the API key. Deployed as a Docker container on Render's free web service tier (no credit card). Free instances have 512 MB RAM and 0.1 CPU, spin down after 15 minutes idle, take about a minute to wake, and lose local disk on every spin-down. Design around those limits. Do not use a platform that needs a paid plan or a card.
- FastF1, pandas, statsmodels and matplotlib must run in the Python backend. Do not try to run them in Next.js or Vercel serverless functions.

Repo layout (monorepo):

```
pitwall/
  backend/
    app/
      main.py          # FastAPI app, routes, CORS, rate limiting
      tools.py         # get_stints, fit_degradation, compare_drivers (moved from pitwall.py)
      agent.py         # Gemini client, chat sessions, system prompt
      races.py         # allowed races list + validation helpers
    preload.py         # downloads/caches the allowed races at build time
    requirements.txt
    Dockerfile
  frontend/            # Next.js app
  pitwall.py           # original prototype, kept for reference
  README.md
```

## 4. Backend spec

### Endpoints
- `GET /health` returns `{"status": "ok"}`. The frontend pings it on page load to wake a sleeping free-tier server.
- `GET /api/races` returns the allowed races (year, race name, display label) so the UI can show example prompts.
- `POST /api/chat` takes `{session_id, message}` and returns `{reply, plots, tool_calls}`:
  - `reply`: the assistant text.
  - `plots`: list of `{url, caption}` for any plot the tools produced during this request.
  - `tool_calls`: list of `{name, args, ok}` so the UI can show "Ran fit_degradation(HAM, stint 2)"
    and distinguish a failed call (`ok: false`, e.g. "fit_degradation failed: too few clean laps") from a
    successful one.
- `GET /plots/{filename}` serves saved PNGs via `StaticFiles`.

### Agent
- One Gemini chat session per `session_id`, kept in an in-memory dict with a 30 minute TTL, a cap of 200 sessions, and a cap of 30 messages per session.
- Use the `google-genai` SDK with Python functions as tools (automatic function calling). Check the current docs for the installed SDK version before writing this.
- Capture plot paths and tool calls per request by wrapping the tools with a `contextvars`-based recorder. The wrappers must preserve the original signatures and docstrings (use `functools.wraps`, then verify the SDK still builds the schema correctly).
- Keep the existing system prompt rules: answer only from tool output, never invent lap times or causes, use three-letter driver codes, ask for year or race if missing, repeat the tool caveat when reporting degradation, mention the plot.
- Free-tier quota is the main constraint. One chat message can trigger several Gemini requests (one per tool round), and free daily request limits are small, especially on full Flash models. Use a Flash-Lite model by default (model name comes from `GEMINI_MODEL`), confirm it supports function calling, and add a global daily request cap in the backend that returns a friendly "demo is busy, try again tomorrow" message before Google's quota errors do.
- Streaming is a nice-to-have. If the installed SDK supports streaming together with automatic function calling, stream over SSE. If not, return the full response and let the frontend animate it. Do not spend long on this.

### Data and performance
- Tools are blocking. Use plain `def` endpoints (FastAPI runs them in a threadpool) or `run_in_threadpool`.
- Add a per-race lock so two simultaneous requests do not download the same session twice.
- Keep an LRU cache of at most 2 loaded sessions in memory. The free instance has only 512 MB RAM, so measure memory use with a real race loaded and reduce the cache to 1 if it gets close.
- Load sessions with `telemetry=False, weather=False, messages=False`.
- `preload.py` loads every allowed race into the FastF1 cache. Run it during the Docker build so the cache is baked into the image (free-tier disks are ephemeral).

### Allowed races
Restrict the public app to a small fixed list, defined in `races.py`. Start with these candidates, then verify each one loads and was mostly dry, and swap any that are not:
- Silverstone 2023
- Monza 2023
- Suzuka 2024
- Bahrain 2024

Validate on the server, not just in the prompt: reject any year/race not in the list, driver codes that are not three letters or not in that race, and stint numbers outside a sane range. Tools should return `{"error": "..."}` with a clear message instead of raising.

### Security and abuse protection
- API key only in an environment variable, never in code, logs or the frontend.
- CORS restricted to the deployed frontend origin (and localhost in dev).
- Rate limit per IP (for example 20 chat requests per hour, tune this) using `slowapi` or a small in-memory limiter.
- Max message length 500 characters. Cap the number of tool calls per request.
- No arbitrary file paths from user input anywhere.

## 5. Frontend spec

- Dark, clean, minimal design that looks like a product, not a data-science demo. Use the `frontend-design` skill if available.
- Single page with a chat layout: message list, input box, send button.
- Row of clickable example prompts (built from `/api/races`) shown when the chat is empty, so a first-time visitor can get an answer in one click.
- Assistant messages render Markdown and show any returned plots inline as images with captions.
- Show a subtle line for each tool call ("Ran fit_degradation for HAM, stint 2").
- Loading states: on page load ping `/health` and show "Waking up the server" if it is slow. While a race loads for the first time, show "Loading race data, this can take up to a minute."
- Clear error state for rate limits, timeouts and backend errors.
- Mobile responsive.
- `session_id` is a UUID generated client-side and held in memory.
- Backend URL comes from `NEXT_PUBLIC_API_URL`.
- Small footer: what it is, that it uses FastF1 data, and that degradation figures are approximate.

## 6. Phases and checkpoints

**Phase 0: verify the prototype.** Install dependencies, run `pitwall.py` against one allowed race, and fix any real bugs. Show me one working output for each tool. Do not proceed until all three tools return sensible results.

**Phase 1: backend.** Restructure into `backend/app`, add the endpoints, validation, session handling and plot capture. Provide a `curl` or PowerShell example for each endpoint and a small smoke-test script that calls every tool on every allowed race. Checkpoint: I can call `/api/chat` locally and get a reply with a plot URL.

**Phase 2: frontend.** Build the chat UI against the local backend. Checkpoint: I can run both locally and have a full conversation with inline plots.

**Phase 3: hardening.** Rate limiting, CORS, input limits, caching, error states, the preload script and cold-start handling.

**Phase 4: deploy.** Dockerfile for the backend with the cache baked in, deploy backend and frontend, set environment variables, wire CORS to the real frontend URL. Give me a step-by-step checklist for anything that has to be done in a dashboard by hand. Checkpoint: the live URL works from my phone.

**Phase 5: README.** Include a screenshot or GIF, a short architecture diagram (Mermaid is fine), how to run it locally, and the limitations section below.

## 7. Cost, honesty and scope rules

- Everything must run at $0 on free tiers with no credit card: Vercel Hobby (frontend), Render free web service (backend), the Gemini API free tier, and FastF1's public data. Never add a paid service or paid dependency.
- Never enable billing on the Google Cloud project behind the Gemini key. With no billing attached, hitting the free-tier limit just returns errors and cannot charge me. The backend must handle those quota errors gracefully and show the visitor a friendly "the demo is busy, try again later" message.
- This project is an LLM front end over FastF1 analysis tools. Do not describe it as containing reinforcement learning, a race simulator or strategy optimisation. Those do not exist.
- The README and footer must state that degradation figures are approximate and that the fuel correction is an assumed constant.
- Keep v1 small. No accounts, saved history, databases or extra tools until everything above is deployed and working.
- If you are unsure about something, ask me instead of guessing. If a library API differs from what you expect, check the current docs.

## 8. Definition of done

- Live frontend URL that works on desktop and mobile.
- A first-time visitor can click an example prompt and get an answer with a plot in under a minute, including a cold start.
- Tools reject anything outside the allowed races.
- No secrets in the repo or the browser.
- README with screenshot, architecture diagram, run instructions and limitations.
