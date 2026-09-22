import type { ToolCall } from "@/lib/types";
import { toolCallLabel } from "@/lib/toolCallLabel";

export function ToolCallLine({ call }: { call: ToolCall }) {
  return (
    <div
      className={`flex items-center gap-1.5 text-xs ${
        call.ok ? "text-slate-500" : "text-red-400/80"
      }`}
    >
      <span aria-hidden>{call.ok ? "✓" : "✗"}</span>
      <span>{toolCallLabel(call)}</span>
      {!call.ok && <span className="text-slate-500">(failed)</span>}
    </div>
  );
}
