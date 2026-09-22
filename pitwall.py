"""
Pit Wall: an LLM that answers F1 race questions by calling real analysis tools
over FastF1 data. The model does no maths. It picks tools and explains results.

Setup:
    pip install fastf1 pandas numpy statsmodels matplotlib google-genai
    set GEMINI_API_KEY=your_key            (Windows cmd)
    export GEMINI_API_KEY=your_key         (mac/linux)
    python pitwall.py                      (lists available Flash models)
    set GEMINI_MODEL=<model name from that list>
    python pitwall.py

Try:
    How many stops did VER make at Silverstone 2023, and on what tyres?
    Fit tyre degradation for HAM's second stint at Monza 2023.
    Compare NOR and PIA's pace and strategy at Suzuka 2024.
"""
import os

import matplotlib

matplotlib.use("Agg")  # save plots to files, no GUI windows
import matplotlib.pyplot as plt
import pandas as pd
import statsmodels.api as sm
import fastf1
from google import genai
from google.genai import types

MODEL = os.environ.get("GEMINI_MODEL")  # required, see main()
CACHE_DIR = "f1_cache"
PLOT_DIR = "plots"

# Rough assumption: a car gets faster as fuel burns off. Tune or replace later.
FUEL_EFFECT_S_PER_LAP = 0.05

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

_sessions = {}


# ---------------------------------------------------------------- helpers
def _load(year, race):
    key = (year, race.lower())
    if key not in _sessions:
        s = fastf1.get_session(year, race, "R")
        # get_session fuzzy-matches, so "Atlantis" silently becomes some other GP.
        # Insist the name the user gave actually appears in the event it picked.
        ev = s.event
        names = [str(ev[c]).lower() for c in ("EventName", "Location", "Country", "OfficialEventName")]
        if not any(race.lower() in n for n in names):
            raise ValueError(f"Could not find a race matching '{race}' in {year}.")
        s.load(telemetry=False, weather=False, messages=False)
        _sessions[key] = s
    return _sessions[key]


def _suspended_windows(session):
    """(start, end) session-time windows when the race was red-flagged."""
    windows, start = [], None
    for _, row in session.session_status.iterrows():
        if row["Status"] == "Aborted":
            start = row["Time"]
        elif row["Status"] == "Started" and start is not None:
            windows.append((start, row["Time"]))
            start = None
    if start is not None:  # red flag and the race never restarted
        windows.append((start, pd.Timedelta.max))
    return windows


def _in_windows(t, windows):
    return pd.notna(t) and any(a <= t <= b for a, b in windows)


def _merge_red_flag_stints(laps, windows):
    """FastF1 starts a new Stint when a car enters the pits under a red flag,
    even if it keeps the same tyres. Merge those so they are not counted as
    race stops. A red-flag tyre change (new compound or age reset) stays separate.
    Also renumbers Stint 1..n."""
    laps = laps.sort_values("LapNumber").copy()
    numbers, current, prev = [], 0, None
    for _, lap in laps.iterrows():
        if prev is None:
            current = 1
        elif lap["Stint"] != prev["Stint"]:
            red = _in_windows(prev["PitInTime"], windows)
            same_tyres = lap["Compound"] == prev["Compound"] and lap["TyreLife"] > prev["TyreLife"]
            if not (red and same_tyres):
                current += 1
        numbers.append(current)
        prev = lap
    laps["Stint"] = numbers
    return laps


def _driver_laps(session, driver):
    laps = session.laps
    laps = laps[laps["Driver"] == driver.upper()]
    if laps.empty:
        drivers = ", ".join(sorted(session.laps["Driver"].dropna().unique()))
        raise ValueError(
            f"No laps found for driver code {driver.upper()} in this race. Drivers with laps: {drivers}"
        )
    return _merge_red_flag_stints(laps, _suspended_windows(session))


def _clean(laps):
    """Keep representative laps: accurate, green flag, not in/out laps."""
    ok = laps["IsAccurate"].fillna(False).astype(bool)
    ok &= laps["TrackStatus"] == "1"
    ok &= laps["PitInTime"].isna() & laps["PitOutTime"].isna()
    laps = laps[ok]
    return laps.dropna(subset=["LapTime", "TyreLife"])


def _int(x):
    return int(x) if pd.notna(x) else None


def _degradation_warnings(laps, x, y, fit, raw_slope):
    """Flag fits that likely don't reflect real tyre wear, so the LLM can
    surface the caveat instead of reading the slope at face value."""
    warnings = []

    if len(laps) < 10:
        warnings.append(f"Only {len(laps)} clean laps in this stint; the fit rests on a small sample.")

    if fit.rsquared < 0.3:
        warnings.append(
            f"Weak fit (R^2={fit.rsquared:.2f}): tyre age alone explains little of the lap time variation."
        )

    std_err = float(fit.bse["TyreLife"])
    if std_err > 0 and abs(raw_slope) < 2 * std_err:
        warnings.append(
            "The slope is not statistically distinguishable from zero (its standard error is "
            "large relative to its size)."
        )

    # A stint's last clean lap being much slower than the rest is usually a missed
    # in-lap, fuel-saving, or a car being held up late on, not tyre wear.
    order = x.argsort()
    y_sorted = y.iloc[order].to_numpy()
    if len(y_sorted) >= 4:
        last, rest_median = y_sorted[-1], float(pd.Series(y_sorted[:-1]).median())
        if last - rest_median > 1.0:
            warnings.append(
                f"The last lap of this stint ({last:.2f}s) is {last - rest_median:.1f}s slower than "
                "the rest of the stint, which usually means a missed in-lap or fuel saving, not "
                "tyre wear."
            )

    return warnings


# ------------------------------------------------------------------ tools
def get_stints(year: int, race: str, driver: str) -> dict:
    """List a driver's tyre stints in a race.

    Args:
      year: Season year, e.g. 2023.
      race: Grand Prix name or location, e.g. "Silverstone" or "Monza".
      driver: Three-letter driver code, e.g. "VER", "HAM".
    """
    try:
        laps = _driver_laps(_load(year, race), driver)
        stints = []
        for n, g in laps.groupby("Stint"):
            stints.append(
                {
                    "stint": int(n),
                    "compound": str(g["Compound"].iloc[0]),
                    "first_lap": _int(g["LapNumber"].min()),
                    "last_lap": _int(g["LapNumber"].max()),
                    "laps": int(len(g)),
                    "tyre_age_at_start": _int(g["TyreLife"].iloc[0]),
                }
            )
        return {"driver": driver.upper(), "stints": stints}
    except Exception as e:
        return {"error": str(e)}


def fit_degradation(year: int, race: str, driver: str, stint: int) -> dict:
    """Fit tyre degradation (seconds lost per lap of tyre age) for one stint
    and save a plot of lap time against tyre age.

    Args:
      year: Season year, e.g. 2023.
      race: Grand Prix name or location.
      driver: Three-letter driver code.
      stint: Stint number as returned by get_stints (1 is the first stint).
    """
    try:
        all_laps = _driver_laps(_load(year, race), driver)
        n_stints = int(all_laps["Stint"].max())
        if not 1 <= stint <= n_stints:
            return {"error": f"{driver.upper()} has {n_stints} stints, so stint {stint} does not exist."}
        laps = _clean(all_laps)
        laps = laps[laps["Stint"] == stint]
        if len(laps) < 6:
            return {"error": f"Only {len(laps)} clean laps in that stint, too few to fit."}

        y = laps["LapTime"].dt.total_seconds()
        x = laps["TyreLife"].astype(float)
        fit = sm.OLS(y, sm.add_constant(x)).fit()
        raw = float(fit.params["TyreLife"])
        warnings = _degradation_warnings(laps, x, y, fit, raw)

        fig, ax = plt.subplots(figsize=(7, 4))
        ax.scatter(x, y, s=18)
        ax.plot(x, fit.predict(sm.add_constant(x)), color="red")
        ax.set_xlabel("Tyre age (laps)")
        ax.set_ylabel("Lap time (s)")
        compound = str(laps["Compound"].iloc[0])
        ax.set_title(f"{driver.upper()} stint {stint} ({compound}), {race} {year}")
        path = os.path.join(PLOT_DIR, f"{driver.upper()}_{year}_{race}_stint{stint}.png")
        fig.tight_layout()
        fig.savefig(path, dpi=130)
        plt.close(fig)

        return {
            "driver": driver.upper(),
            "stint": stint,
            "compound": compound,
            "clean_laps_used": int(len(laps)),
            "raw_slope_s_per_lap": round(raw, 4),
            "fuel_corrected_slope_s_per_lap": round(raw + FUEL_EFFECT_S_PER_LAP, 4),
            "slope_std_error": round(float(fit.bse["TyreLife"]), 4),
            "r_squared": round(float(fit.rsquared), 3),
            "plot_saved_to": path,
            "warnings": warnings,
            "caveat": (
                "Within one stint, tyre age and fuel load move together, so they cannot be "
                f"separated statistically. The fuel-corrected figure assumes {FUEL_EFFECT_S_PER_LAP} "
                "s/lap of fuel benefit, which is an approximation."
            ),
        }
    except Exception as e:
        return {"error": str(e)}


def compare_drivers(year: int, race: str, driver_a: str, driver_b: str) -> dict:
    """Compare two drivers' race pace and strategy.

    Args:
      year: Season year, e.g. 2023.
      race: Grand Prix name or location.
      driver_a: Three-letter code of the first driver.
      driver_b: Three-letter code of the second driver.
    """
    try:
        session = _load(year, race)
        windows = _suspended_windows(session)
        out = {}
        for d in (driver_a, driver_b):
            d = d.upper()
            laps = _driver_laps(session, d)
            clean = _clean(laps)
            res = session.results
            row = res[res["Abbreviation"] == d]
            pit_in = laps[laps["PitInTime"].notna()]
            red = pit_in["PitInTime"].apply(lambda t: _in_windows(t, windows))
            pit_laps = pit_in.loc[~red, "LapNumber"]
            out[d] = {
                "finish_position": _int(row["Position"].iloc[0]) if len(row) else None,
                "median_clean_lap_s": round(float(clean["LapTime"].dt.total_seconds().median()), 3),
                "clean_laps": int(len(clean)),
                "pit_stops": int(len(pit_laps)),
                "pit_laps": [int(p) for p in pit_laps],
                "red_flag_pit_laps": [int(p) for p in pit_in.loc[red, "LapNumber"]],
                "compounds_in_order": [str(c) for c in laps.groupby("Stint")["Compound"].first()],
            }
        a, b = driver_a.upper(), driver_b.upper()
        out["median_pace_gap_s"] = round(
            out[a]["median_clean_lap_s"] - out[b]["median_clean_lap_s"], 3
        )
        out["note"] = (
            "Positive gap means driver_a was slower. Median pace mixes different "
            "compounds and fuel loads, so treat it as a rough comparison."
        )
        return out
    except Exception as e:
        return {"error": str(e)}


# ------------------------------------------------------------------ agent
SYSTEM = """You are a Formula 1 race analyst. You answer questions about past races
using ONLY the results of the tools you are given. Rules:
- Use three-letter driver codes (VER, HAM, NOR...) when calling tools.
- If the year or race is missing from the question, ask for it before calling tools.
- Never invent lap times, strategies or causes. If the tool data cannot support a claim, say so.
- When you report degradation, mention the caveat returned by the tool, and mention every
  item in its "warnings" list if it is non-empty (for example a weak fit or a small sample).
- If a plot was saved, tell the user the file path.
- Keep answers short and concrete."""


def main():
    client = genai.Client()  # reads GEMINI_API_KEY from the environment
    if not MODEL:
        print("Set GEMINI_MODEL to one of these Flash models, then run again:")
        for m in client.models.list():
            if "flash" in m.name.lower():
                print("   ", m.name.replace("models/", ""))
        return
    chat = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            tools=[get_stints, fit_degradation, compare_drivers],
            temperature=0.2,
        ),
    )
    print(f"Pit Wall ready (model: {MODEL}). Type 'exit' to quit.")
    print("First load of a race downloads data and can take a minute.")
    while True:
        q = input("\nAsk the pit wall > ").strip()
        if q.lower() in {"exit", "quit"}:
            break
        if not q:
            continue
        try:
            print(chat.send_message(q).text)
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()