"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatMessage, Race } from "@/lib/types";
import { ApiError, getHealth, getRaces, postChat } from "@/lib/api";
import { MessageBubble } from "./MessageBubble";
import { ExamplePrompts } from "./ExamplePrompts";
import { ChatInput } from "./ChatInput";
import { Footer } from "./Footer";

type ServerStatus = "checking" | "waking" | "ready" | "unreachable";

// If /health hasn't resolved by the time this elapses, the free-tier
// instance is probably asleep and mid-wake, so switch the banner to say so
// instead of leaving the visitor looking at a blank, silent page.
const WAKING_BANNER_DELAY_MS = 1_500;
// If a chat request is still in flight after this long, it's more likely a
// first-time race load (which CLAUDE.md says can take up to a minute) than
// ordinary Gemini latency, so the loading line changes to explain that.
const RACE_LOADING_HINT_DELAY_MS = 8_000;

function errorMessageFor(err: unknown): string {
  if (err instanceof ApiError) {
    switch (err.kind) {
      case "timeout":
        return "The request timed out. The server might be waking up, or a race is loading for the first time -- please try again.";
      case "network":
        return "Could not reach the server. Check your connection and try again.";
      case "rate_limited":
      case "busy":
      case "session_limit":
        return err.message;
      case "validation":
        return "That message wasn't accepted -- please shorten it and try again.";
      default:
        return err.message || "Something went wrong. Please try again.";
    }
  }
  return "Something went wrong. Please try again.";
}

export function ChatApp() {
  const sessionId = useRef<string>(crypto.randomUUID());

  const [serverStatus, setServerStatus] = useState<ServerStatus>("checking");
  const [races, setRaces] = useState<Race[]>([]);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [sendingSlow, setSendingSlow] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const wakingTimer = setTimeout(() => {
      setServerStatus((s) => (s === "checking" ? "waking" : s));
    }, WAKING_BANNER_DELAY_MS);

    getHealth().then((ok) => {
      clearTimeout(wakingTimer);
      setServerStatus(ok ? "ready" : "unreachable");
    });

    getRaces()
      .then(setRaces)
      .catch(() => setRaces([]));

    return () => clearTimeout(wakingTimer);
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || trimmed.length > 500 || sending) return;

    setMessages((m) => [...m, { id: crypto.randomUUID(), role: "user", content: trimmed }]);
    setInput("");
    setSending(true);

    const slowTimer = setTimeout(() => setSendingSlow(true), RACE_LOADING_HINT_DELAY_MS);

    try {
      const res = await postChat(sessionId.current, trimmed);
      setMessages((m) => [
        ...m,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: res.reply,
          plots: res.plots,
          toolCalls: res.tool_calls,
        },
      ]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        { id: crypto.randomUUID(), role: "error", content: errorMessageFor(err) },
      ]);
    } finally {
      clearTimeout(slowTimer);
      setSending(false);
      setSendingSlow(false);
    }
  }

  return (
    <div className="flex h-dvh flex-col bg-slate-950">
      <header className="border-b border-slate-800 px-4 py-3">
        <div className="mx-auto flex max-w-3xl items-baseline gap-2">
          <h1 className="text-base font-semibold text-white">Pit Wall</h1>
          <span className="text-xs text-slate-500">real F1 race analysis, plain English</span>
        </div>
      </header>

      {serverStatus === "waking" && (
        <div className="border-b border-amber-900/50 bg-amber-950/30 px-4 py-2 text-center text-xs text-amber-300">
          Waking up the server -- this can take up to a minute on the free tier.
        </div>
      )}
      {serverStatus === "unreachable" && (
        <div className="border-b border-red-900/50 bg-red-950/30 px-4 py-2 text-center text-xs text-red-300">
          Can&apos;t reach the server right now. Try refreshing in a moment.
        </div>
      )}

      <div ref={scrollRef} className="thin-scrollbar flex-1 overflow-y-auto">
        <div className="mx-auto flex min-h-full max-w-3xl flex-col justify-end gap-4 px-3 py-4 sm:px-4">
          {messages.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-4 py-10 text-center">
              <p className="max-w-sm text-sm text-slate-400">
                Ask a question about one of these races and Pit Wall will call real analysis
                tools over FastF1 data to answer it.
              </p>
              {races.length > 0 && <ExamplePrompts races={races} onPick={send} />}
            </div>
          ) : (
            messages.map((m) => <MessageBubble key={m.id} message={m} />)
          )}

          {sending && (
            <div className="flex justify-start">
              <div className="rounded-2xl rounded-bl-sm border border-slate-800 bg-slate-900 px-4 py-2.5 text-sm text-slate-400">
                {sendingSlow
                  ? "Loading race data, this can take up to a minute the first time…"
                  : "Thinking…"}
              </div>
            </div>
          )}
        </div>
      </div>

      <ChatInput value={input} onChange={setInput} onSend={() => send(input)} disabled={sending} />
      <Footer />
    </div>
  );
}
