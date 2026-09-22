// Mirrors the shapes returned by the FastAPI backend (see backend/app/main.py
// and backend/app/agent.py). Keep in sync with those by hand -- there's no
// shared schema between the two halves of this repo yet.

export type Race = {
  year: number;
  race: string;
  label: string;
};

export type Plot = {
  url: string;
  caption: string;
};

export type ToolCall = {
  name: string;
  args: Record<string, unknown>;
  ok: boolean;
};

export type ChatApiResponse = {
  reply: string;
  plots: Plot[];
  tool_calls: ToolCall[];
};

export type ChatMessage =
  | { id: string; role: "user"; content: string }
  | {
      id: string;
      role: "assistant";
      content: string;
      plots: Plot[];
      toolCalls: ToolCall[];
    }
  | { id: string; role: "error"; content: string };
