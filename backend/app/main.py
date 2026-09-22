"""FastAPI app: health check, allowed-races listing, chat, and static plot
serving.

Run locally from the backend/ directory:
    uvicorn app.main:app --reload --port 8000

Rate limiting, the deployed frontend's CORS origin, request-length limits
beyond the chat message cap, and the preload script are Phase 3 work (see
CLAUDE.md) -- this is enough to run the backend locally and, in Phase 2,
against a local Next.js dev server.
"""
import os

from dotenv import load_dotenv

# Must run before importing agent, which reads GEMINI_API_KEY/GEMINI_MODEL
# from the environment at import time. Loads backend/.env for local dev;
# a no-op if the file doesn't exist (e.g. in production, where the real
# platform sets these as actual environment variables).
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agent, races, tools

app = FastAPI(title="Pit Wall API")

app.add_middleware(
    CORSMiddleware,
    # Local dev origins only for now; Phase 3 adds the deployed frontend's
    # real origin via an env var.
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
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
def chat(req: ChatRequest):
    try:
        reply, tool_calls, plots = agent.send_message(req.session_id, req.message)
    except agent.SessionLimitReached as e:
        raise HTTPException(status_code=400, detail=str(e))
    except agent.QuotaExceeded as e:
        raise HTTPException(status_code=503, detail=str(e))
    except agent.AgentNotConfigured as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"reply": reply, "plots": plots, "tool_calls": tool_calls}
