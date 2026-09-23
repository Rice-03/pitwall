# Pit Wall backend. Built and run from the backend/ directory (Render's
# "Root Directory" setting, see the Phase 4 deploy checklist in the repo
# README) -- everything this image needs is self-contained under backend/.
FROM python:3.13-slim

WORKDIR /app

# Install dependencies first, in their own layer, so a code-only change
# doesn't invalidate the (slow) dependency install on the next build.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app app
COPY preload.py .

# Bakes the FastF1 cache for all 4 allowed races into the image. Render's
# free-tier disk is ephemeral, so without this every cold start would
# re-download every race the first time someone asks about it -- exactly
# the slow first-ask experience CLAUDE.md's cold-start handling is meant to
# avoid. FASTF1_CACHE_DIR matches app/tools.py's own default.
ENV FASTF1_CACHE_DIR=/app/f1_cache
RUN python preload.py

# Render sets PORT (default 10000) and routes through its own proxy, so the
# app needs to both bind to $PORT and trust the proxy's forwarded headers
# (get_remote_address in main.py's rate limiter would otherwise see Render's
# proxy IP for every visitor instead of their real one). Shell form so
# $PORT is substituted at container start, not at build time.
EXPOSE 10000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers --forwarded-allow-ips='*'
