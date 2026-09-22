"""Calls every tool on every allowed race, plus a few validation edge cases.

No Gemini calls -- this exercises tools.py and races.py directly, the same
way Phase 0 tested the prototype, so it costs nothing against the API quota.

Run from backend/:
    ..\\.venv\\Scripts\\python.exe smoke_test_tools.py     (PowerShell/cmd)
    ../.venv/Scripts/python.exe smoke_test_tools.py         (Git Bash)
"""
import json
import sys
import time

sys.path.insert(0, ".")
from app import races, tools

PASS, FAIL = 0, 0


def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}  {detail}")


def main():
    # VER and PER raced for the same team across all four events, so they're
    # a safe pair to smoke-test get_stints/compare_drivers on every race.
    for entry in races.list_races():
        year, race, label = entry["year"], entry["race"], entry["label"]
        print(f"\n=== {label} ===")
        t0 = time.time()

        r = tools.get_stints(year, race, "VER")
        check("get_stints(VER)", "error" not in r and len(r.get("stints", [])) > 0, r)

        r2 = tools.compare_drivers(year, race, "VER", "PER")
        check(
            "compare_drivers(VER, PER)",
            "error" not in r2 and "median_pace_gap_s" in r2,
            r2,
        )

        rf = tools.fit_degradation(year, race, "VER", 1)
        check(
            "fit_degradation(VER, stint 1)",
            "error" not in rf and isinstance(rf.get("raw_slope_s_per_lap"), float),
            rf,
        )

        print(f"  ({time.time() - t0:.1f}s)")

    print("\n=== validation edge cases ===")
    check("unknown race rejected", "error" in tools.get_stints(2023, "Atlantis", "VER"))
    check("unlisted year rejected", "error" in tools.get_stints(2024, "Monza", "VER"))
    check("bad driver code rejected", "error" in tools.get_stints(2023, "Monza", "XX1"))
    check("nonexistent driver in race", "error" in tools.get_stints(2023, "Monza", "TSU"))
    check("stint 0 rejected", "error" in tools.fit_degradation(2023, "Monza", "VER", 0))
    check("stint out of range rejected", "error" in tools.fit_degradation(2023, "Monza", "VER", 99))
    check(
        "compare_drivers bad driver rejected",
        "error" in tools.compare_drivers(2023, "Monza", "VER", "ZZ"),
    )

    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
