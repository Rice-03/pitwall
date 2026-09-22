import type { Race } from "@/lib/types";
import { examplePromptFor } from "@/lib/examplePrompts";

export function ExamplePrompts({
  races,
  onPick,
}: {
  races: Race[];
  onPick: (prompt: string) => void;
}) {
  return (
    <div className="flex flex-wrap justify-center gap-2 px-4">
      {races.map((race) => {
        const prompt = examplePromptFor(race);
        return (
          <button
            key={`${race.year}-${race.race}`}
            onClick={() => onPick(prompt)}
            className="rounded-full border border-slate-700 bg-slate-900 px-3.5 py-1.5 text-left text-sm text-slate-300 transition-colors hover:border-sky-700 hover:bg-slate-800 hover:text-white"
          >
            {prompt}
          </button>
        );
      })}
    </div>
  );
}
