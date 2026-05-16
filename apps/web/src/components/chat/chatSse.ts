export type ChatSseEventType =
  | "message"
  | "tool_call"
  | "generation_started"
  | "generation_complete"
  | "error";

export type ChatSseEvent = {
  type: ChatSseEventType;
  data: Record<string, unknown>;
};

const CHAT_EVENT_TYPES = new Set<string>([
  "message",
  "tool_call",
  "generation_started",
  "generation_complete",
  "error",
]);

export function createChatSseParser() {
  let buffer = "";

  return {
    push(chunk: string): ChatSseEvent[] {
      buffer += chunk.replace(/\r\n/g, "\n");
      const events: ChatSseEvent[] = [];

      while (true) {
        const boundary = buffer.indexOf("\n\n");
        if (boundary < 0) break;

        const rawEvent = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const parsed = parseSseEvent(rawEvent);
        if (parsed) events.push(parsed);
      }

      return events;
    },
  };
}

function parseSseEvent(rawEvent: string): ChatSseEvent | null {
  let eventType = "";
  const dataLines: string[] = [];

  for (const rawLine of rawEvent.split(/\r?\n/)) {
    const line = rawLine.trimEnd();
    if (line.startsWith("event:")) {
      eventType = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }

  if (!CHAT_EVENT_TYPES.has(eventType) || dataLines.length === 0) {
    return null;
  }

  try {
    const data = JSON.parse(dataLines.join("\n"));
    if (data && typeof data === "object" && !Array.isArray(data)) {
      return { type: eventType as ChatSseEventType, data };
    }
  } catch {
    return null;
  }

  return null;
}
