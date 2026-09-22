"""The fixed, hand-picked list of races this public demo supports.

Restricting to a short allow-list -- rather than letting the LLM pass any
year/race string straight into FastF1 -- is what makes an unattended public
app safe: nobody can make the backend try to download and analyse an
arbitrary session, and every tool can reject bad input before it does any
real work.

All four were checked before being added here (dry race, and if a red flag
or safety car occurred, that it doesn't gut per-stint clean-lap counts -- see
the Phase 0 write-up):
  - Silverstone 2023: dry, one ~12 min safety car, no red flag.
  - Monza 2023: dry, one brief yellow, no red flag.
  - Suzuka 2024: dry, but red-flagged on lap 1. Kept deliberately as a
    realistic edge case -- get_stints/compare_drivers already merge the
    red-flag pit visit correctly (see tools._merge_red_flag_stints), and
    fit_degradation returns a clear error or a "thin sample" warning on the
    red-flag-shortened opening stints instead of a misleadingly confident fit.
  - Bahrain 2024: dry, a few brief yellows, no red flag.
"""
import re

ALLOWED_RACES = [
    {
        "year": 2023,
        "race": "Silverstone",
        "label": "British GP 2023 (Silverstone)",
        "aliases": ["silverstone", "british", "britain", "uk", "great britain"],
    },
    {
        "year": 2023,
        "race": "Monza",
        "label": "Italian GP 2023 (Monza)",
        "aliases": ["monza", "italian", "italy"],
    },
    {
        "year": 2024,
        "race": "Suzuka",
        "label": "Japanese GP 2024 (Suzuka)",
        "aliases": ["suzuka", "japanese", "japan"],
    },
    {
        "year": 2024,
        "race": "Bahrain",
        "label": "Bahrain GP 2024 (Sakhir)",
        "aliases": ["bahrain", "sakhir"],
    },
]

DRIVER_CODE_RE = re.compile(r"^[A-Za-z]{3}$")
MAX_STINT = 10  # generous upper bound; a normal race has 1-5 stints


def find_race(year, race):
    """Return the matching ALLOWED_RACES entry for (year, race), or None.

    `race` is matched case-insensitively against the canonical name or the
    alias list, so "silverstone", "Silverstone" and "British Grand Prix" all
    resolve to the same entry.
    """
    try:
        year = int(year)
    except (TypeError, ValueError):
        return None
    if not isinstance(race, str) or not race.strip():
        return None
    q = race.strip().lower()
    for entry in ALLOWED_RACES:
        if entry["year"] == year and (q == entry["race"].lower() or q in entry["aliases"]):
            return entry
    return None


def is_valid_driver_code(code):
    return isinstance(code, str) and bool(DRIVER_CODE_RE.fullmatch(code.strip()))


def is_valid_stint(stint):
    return isinstance(stint, int) and not isinstance(stint, bool) and 1 <= stint <= MAX_STINT


def list_races():
    """Public shape for GET /api/races: no internal alias list."""
    return [{"year": e["year"], "race": e["race"], "label": e["label"]} for e in ALLOWED_RACES]
