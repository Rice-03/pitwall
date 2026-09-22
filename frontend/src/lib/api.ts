import type { ChatApiResponse, Race } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

// Plot URLs come back from the backend as paths relative to its own origin
// (e.g. "/plots/HAM_2023_Monza_stint2.png"), so the frontend has to prefix
// them with the same API_URL it used for the chat request.
export function plotUrl(path: string): string {
  return `${API_URL}${path}`;
}

export type ApiErrorKind =
  | "timeout"
  | "network"
  | "rate_limited"
  | "busy"
  | "session_limit"
  | "server_error"
  | "validation"
  | "unknown";

export class ApiError extends Error {
  kind: ApiErrorKind;

  constructor(kind: ApiErrorKind, message: string) {
    super(message);
    this.kind = kind;
    this.name = "ApiError";
  }
}

async function withTimeout<T>(
  timeoutMs: number,
  run: (signal: AbortSignal) => Promise<T>
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await run(controller.signal);
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new ApiError("timeout", "The server took too long to respond.");
    }
    throw new ApiError("network", "Could not reach the server. Check your connection.");
  } finally {
    clearTimeout(timer);
  }
}

// A cold Render free-tier instance can take up to about a minute to wake, so
// health and chat both get a generous timeout; the UI layers its own shorter
// "waking up" / "loading race data" messaging on top of these while they wait.
export async function getHealth(): Promise<boolean> {
  try {
    const res = await withTimeout(65_000, (signal) =>
      fetch(`${API_URL}/health`, { signal })
    );
    return res.ok;
  } catch {
    return false;
  }
}

export async function getRaces(): Promise<Race[]> {
  const res = await withTimeout(15_000, (signal) =>
    fetch(`${API_URL}/api/races`, { signal })
  );
  if (!res.ok) {
    throw new ApiError("server_error", "Could not load the list of races.");
  }
  const data = await res.json();
  return data.races as Race[];
}

export async function postChat(
  sessionId: string,
  message: string
): Promise<ChatApiResponse> {
  const res = await withTimeout(90_000, (signal) =>
    fetch(`${API_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message }),
      signal,
    })
  );

  if (res.ok) {
    return (await res.json()) as ChatApiResponse;
  }

  let detail = "Something went wrong.";
  try {
    const body = await res.json();
    if (typeof body.detail === "string") detail = body.detail;
  } catch {
    // no JSON body, fall back to the generic message
  }

  if (res.status === 429) throw new ApiError("rate_limited", detail);
  if (res.status === 503) throw new ApiError("busy", detail);
  if (res.status === 400) throw new ApiError("session_limit", detail);
  if (res.status === 422) throw new ApiError("validation", detail);
  if (res.status >= 500) throw new ApiError("server_error", detail);
  throw new ApiError("unknown", detail);
}
