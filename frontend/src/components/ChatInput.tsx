"use client";

import { useRef } from "react";

const MAX_LENGTH = 500;

export function ChatInput({
  value,
  onChange,
  onSend,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled: boolean;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const trimmed = value.trim();
  const overLimit = value.length > MAX_LENGTH;
  const canSend = trimmed.length > 0 && !overLimit && !disabled;

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSend) onSend();
    }
  }

  return (
    <div className="border-t border-slate-800 bg-slate-950 px-3 py-3 sm:px-4">
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Ask about a race, e.g. Fit tyre degradation for HAM's second stint at Monza 2023."
          className="max-h-32 min-h-[44px] flex-1 resize-none rounded-xl border border-slate-700 bg-slate-900 px-3.5 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 focus:border-sky-600 focus:outline-none"
        />
        <button
          onClick={onSend}
          disabled={!canSend}
          className="h-[44px] shrink-0 rounded-xl bg-sky-600 px-4 text-sm font-medium text-white transition-colors enabled:hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-500"
        >
          Send
        </button>
      </div>
      <div className="mx-auto mt-1 max-w-3xl px-0.5 text-right text-xs">
        <span className={overLimit ? "text-red-400" : "text-slate-600"}>
          {value.length}/{MAX_LENGTH}
        </span>
      </div>
    </div>
  );
}
