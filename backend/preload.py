"""Loads every allowed race into the FastF1 cache.

Run this during the Docker build (see the Phase 4 Dockerfile) so the cache
is baked into the image -- Render's free-tier disk is ephemeral, so anything
not baked in gets re-downloaded, slowly, on every cold start instead.

Run from backend/:
    ..\\.venv\\Scripts\\python.exe preload.py     (PowerShell/cmd)
    ../.venv/Scripts/python.exe preload.py         (Git Bash)
"""
import sys
import time

sys.path.insert(0, ".")
from app import races, tools


def main():
    for entry in races.list_races():
        year, race, label = entry["year"], entry["race"], entry["label"]
        print(f"Preloading {label}...", flush=True)
        t0 = time.time()
        try:
            tools._load(year, race)
        except Exception as e:
            print(f"  FAILED: {e}", flush=True)
            sys.exit(1)
        print(f"  done in {time.time() - t0:.1f}s", flush=True)

    print("All races cached.", flush=True)


if __name__ == "__main__":
    main()
