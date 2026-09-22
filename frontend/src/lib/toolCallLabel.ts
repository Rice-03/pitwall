import type { ToolCall } from "./types";

// Turns a recorded tool call into the "Ran fit_degradation for HAM, stint 2"
// style line from CLAUDE.md's frontend spec. Falls back to a generic
// name(args) rendering for any tool this doesn't specifically know about, so
// a new tool added later still shows something reasonable.
export function toolCallLabel(call: ToolCall): string {
  const a = call.args as Record<string, unknown>;
  const where = a.race && a.year ? ` at ${a.race} ${a.year}` : "";

  switch (call.name) {
    case "get_stints":
      return `Ran get_stints for ${a.driver}${where}`;
    case "fit_degradation":
      return `Ran fit_degradation for ${a.driver}, stint ${a.stint}${where}`;
    case "compare_drivers":
      return `Ran compare_drivers for ${a.driver_a} vs ${a.driver_b}${where}`;
    default: {
      const args = Object.entries(a)
        .map(([k, v]) => `${k}=${String(v)}`)
        .join(", ");
      return `Ran ${call.name}(${args})`;
    }
  }
}
