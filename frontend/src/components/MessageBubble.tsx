import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "@/lib/types";
import { plotUrl } from "@/lib/api";
import { ToolCallLine } from "./ToolCallLine";

export function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-sky-600 px-4 py-2.5 text-white sm:max-w-[75%]">
          <p className="whitespace-pre-wrap break-words text-sm">{message.content}</p>
        </div>
      </div>
    );
  }

  if (message.role === "error") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-red-900/60 bg-red-950/40 px-4 py-2.5 text-red-200 sm:max-w-[75%]">
          <p className="text-sm">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] space-y-2 sm:max-w-[75%]">
        {message.toolCalls.length > 0 && (
          <div className="space-y-0.5 px-1">
            {message.toolCalls.map((call, i) => (
              <ToolCallLine key={i} call={call} />
            ))}
          </div>
        )}

        <div className="rounded-2xl rounded-bl-sm border border-slate-800 bg-slate-900 px-4 py-2.5">
          <div className="prose prose-invert prose-sm max-w-none prose-p:my-1.5 prose-headings:my-2 prose-ul:my-1.5 prose-ol:my-1.5">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
          </div>
        </div>

        {message.plots.map((plot, i) => (
          <figure
            key={i}
            className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900"
          >
            {/* eslint-disable-next-line @next/next/no-img-element -- plot host
                comes from NEXT_PUBLIC_API_URL and varies by environment, so a
                static next/image remotePatterns allowlist doesn't fit here. */}
            <img src={plotUrl(plot.url)} alt={plot.caption} className="w-full" />
            <figcaption className="border-t border-slate-800 px-3 py-1.5 text-xs text-slate-400">
              {plot.caption}
            </figcaption>
          </figure>
        ))}
      </div>
    </div>
  );
}
