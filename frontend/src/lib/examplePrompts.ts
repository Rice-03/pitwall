import type { Race } from "./types";

// Curated per race so first-time visitors get a genuinely good question
// (matching CLAUDE.md's own examples) rather than a generic template. Falls
// back to a generic-but-still-real question for any race the backend adds
// later that isn't in this list, so the UI never breaks if races.py grows.
const CURATED: Record<string, string> = {
  Silverstone: "How many stops did VER make at Silverstone 2023, and on which tyres?",
  Monza: "Fit tyre degradation for HAM's second stint at Monza 2023.",
  Suzuka: "Compare NOR and PIA's pace and strategy at Suzuka 2024.",
  Bahrain: "How many stops did VER make at Bahrain 2024, and on which tyres?",
};

export function examplePromptFor(race: Race): string {
  return CURATED[race.race] ?? `How many stops did VER make at ${race.label}?`;
}
