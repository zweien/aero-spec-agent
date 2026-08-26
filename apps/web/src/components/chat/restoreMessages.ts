// Rebuilds chat messages (including tool run cards) from the persisted
// conversation history. The backend stores the full message log — assistant
// messages with tool_calls, the tool result messages (job_id, design_id,
// version_no, files) and the final assistant explanation — so a reload can
// restore the interactive run UI instead of dropping everything but text.

export type RestoredToolPart = {
  type: "tool";
  toolCallId: string;
  toolName: string;
  args?: Record<string, unknown>;
  output?: Record<string, unknown>;
  state: "running" | "done";
  runtimeError?: string | null;
};

export type RestoredTextPart = { type: "text"; text: string };

export type RestoredChatMessage = {
  id: string;
  role: "user" | "assistant";
  parts: Array<RestoredTextPart | RestoredToolPart>;
};

export type RawToolCall = {
  id?: string;
  type?: string;
  function?: { name?: string; arguments?: string };
};

export type RawHistoryMessage = {
  role: string;
  content?: string | null;
  tool_calls?: RawToolCall[];
  tool_call_id?: string;
};

function safeParseJson(raw: string | null | undefined): Record<string, unknown> | undefined {
  if (!raw) return undefined;
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : undefined;
  } catch {
    return undefined;
  }
}

function isFailedOutput(output: Record<string, unknown> | undefined): boolean {
  if (!output) return false;
  return (
    output.status === "failed" ||
    Boolean(
      output.job_id &&
        !output.version_no &&
        (output.message || output.error || output.error_message),
    )
  );
}

function buildToolPart(call: RawToolCall, toolMsg: RawHistoryMessage): RestoredToolPart | null {
  const output = safeParseJson(toolMsg.content);
  const toolName = call.function?.name;
  if (!toolName && !output) return null;
  return {
    type: "tool",
    toolCallId: toolMsg.tool_call_id ?? call.id ?? "tool-restored",
    toolName: toolName ?? "generate_design",
    args: safeParseJson(call.function?.arguments),
    output,
    state: "done",
    runtimeError: isFailedOutput(output)
      ? String(output?.error_message ?? output?.error ?? output?.message ?? "生成失败")
      : null,
  };
}

export function restoreMessages(
  rawMsgs: RawHistoryMessage[],
  startId = 1,
): { messages: RestoredChatMessage[]; nextId: number } {
  const messages: RestoredChatMessage[] = [];
  let nextId = startId;
  // The open assistant-with-tool_calls bubble that following tool results and
  // the trailing explanation text merge into.
  let pending: { msg: RestoredChatMessage; calls: RawToolCall[] } | null = null;

  for (const m of rawMsgs) {
    if (m.role === "user") {
      pending = null;
      messages.push({
        id: `msg-${nextId++}`,
        role: "user",
        parts: m.content ? [{ type: "text", text: m.content }] : [],
      });
      continue;
    }

    if (m.role === "assistant") {
      const calls = Array.isArray(m.tool_calls) ? m.tool_calls : [];
      if (calls.length > 0) {
        const msg: RestoredChatMessage = {
          id: `msg-${nextId++}`,
          role: "assistant",
          parts: [],
        };
        messages.push(msg);
        if (m.content) msg.parts.push({ type: "text", text: m.content });
        pending = { msg, calls };
        continue;
      }
      if (m.content) {
        if (pending) {
          // Explanation produced after the tool ran — same bubble.
          pending.msg.parts.push({ type: "text", text: m.content });
        } else {
          messages.push({
            id: `msg-${nextId++}`,
            role: "assistant",
            parts: [{ type: "text", text: m.content }],
          });
        }
      }
      pending = null;
      continue;
    }

    if (m.role === "tool" && pending) {
      const call =
        pending.calls.find((c) => c.id && c.id === m.tool_call_id) ??
        pending.calls[0];
      if (call) {
        const part = buildToolPart(call, m);
        if (part) pending.msg.parts.push(part);
      }
    }
  }

  return { messages, nextId };
}
