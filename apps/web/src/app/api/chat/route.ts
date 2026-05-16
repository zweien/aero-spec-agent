import { type NextRequest } from "next/server";

const FASTAPI_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8900";

const TOOL_LABELS: Record<string, string> = {
  generate_design: "生成设计",
  modify_design: "修改设计",
};

export const dynamic = "force-dynamic";

let globalToolCallCounter = 1;

export async function POST(req: NextRequest) {
  const body = await req.json();
  const messages = body.messages ?? [];
  const conversationId = body.conversation_id ?? "default";

  const lastUserMsg = [...messages]
    .reverse()
    .find((m: { role: string }) => m.role === "user");
  if (!lastUserMsg) {
    return new Response("No user message", { status: 400 });
  }

  const userText: string =
    typeof lastUserMsg.content === "string"
      ? lastUserMsg.content
      : (lastUserMsg.parts ?? [])
          .filter((p: { type: string }) => p.type === "text")
          .map((p: { text: string }) => p.text)
          .join("") || "";

  const fastapiResponse = await fetch(`${FASTAPI_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      conversation_id: conversationId,
      message: userText,
    }),
  });

  if (!fastapiResponse.ok || !fastapiResponse.body) {
    return new Response("Backend error", { status: fastapiResponse.status });
  }

  const encoder = new TextEncoder();
  const reader = fastapiResponse.body.getReader();
  const decoder = new TextDecoder();

  let callCounter = globalToolCallCounter++;
  let currentToolCallId = "";
  let currentToolName = "";
  let toolPhaseTextShown = false;
  let textStarted = false;
  const textId = "text-main";
  const messageId = `msg-${Date.now()}`;
  let sseBuffer = "";
  let done = false;

  function sse(data: object) {
    return encoder.encode(`data: ${JSON.stringify(data)}\n\n`);
  }

  function ensureTextStarted(): Uint8Array {
    if (textStarted) return new Uint8Array();
    textStarted = true;
    return sse({ type: "text-start", id: textId });
  }

  function writeTextDelta(delta: string): Uint8Array {
    const chunks: Uint8Array[] = [];
    const start = ensureTextStarted();
    if (start.length) chunks.push(start);
    chunks.push(sse({ type: "text-delta", id: textId, delta }));
    const total = chunks.reduce((s, c) => s + c.length, 0);
    const result = new Uint8Array(total);
    let offset = 0;
    for (const c of chunks) {
      result.set(c, offset);
      offset += c.length;
    }
    return result;
  }

  function processSSEEvents(): Uint8Array | null {
    const output: Uint8Array[] = [];
    let produced = false;

    const lines = sseBuffer.split("\n");
    sseBuffer = "";

    let eventType = "";
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      if (line.startsWith("event: ")) {
        eventType = line.slice(7).trim();
        continue;
      }

      if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6));
          switch (eventType) {
            case "message": {
              const delta = String(data.content ?? "");
              if (delta) {
                output.push(writeTextDelta(delta));
              }
              break;
            }
            case "tool_call": {
              const toolCallId = `call-${++callCounter}`;
              currentToolCallId = toolCallId;
              currentToolName = String(data.name ?? "");
              toolPhaseTextShown = false;
              let args: Record<string, unknown> = {};
              try {
                args = JSON.parse(String(data.arguments ?? "{}"));
              } catch {
                // keep empty args
              }
              const label = TOOL_LABELS[currentToolName] ?? currentToolName;
              output.push(writeTextDelta(`\n\n> **${label}** `));
              output.push(
                sse({
                  type: "tool-input-available",
                  toolCallId,
                  toolName: currentToolName,
                  input: args,
                }),
              );
              break;
            }
            case "generation_started": {
              if (!toolPhaseTextShown) {
                toolPhaseTextShown = true;
                output.push(writeTextDelta("⚙️ 正在生成CAD模型..."));
              }
              break;
            }
            case "generation_complete": {
              if (currentToolCallId) {
                if (toolPhaseTextShown) {
                  const v = data.version_no;
                  output.push(writeTextDelta(` ✅ v${v}\n\n`));
                }
                output.push(
                  sse({
                    type: "tool-output-available",
                    toolCallId: currentToolCallId,
                    output: data,
                  }),
                );
              }
              break;
            }
            case "error": {
              const errMsg = String(data.content ?? "未知错误");
              output.push(writeTextDelta(`\n\n❌ **错误**: ${errMsg}\n\n`));
              break;
            }
          }
        } catch {
          // skip
        }
        eventType = "";
        continue;
      }

      // Empty line = end of SSE event, or trailing content
      if (line === "") {
        eventType = "";
        continue;
      }

      // Incomplete trailing data
      sseBuffer = line;
    }

    if (output.length === 0) return null;
    produced = true;
    const total = output.reduce((s, c) => s + c.length, 0);
    const result = new Uint8Array(total);
    let offset = 0;
    for (const c of output) {
      result.set(c, offset);
      offset += c.length;
    }
    return result;
  }

  const stream = new ReadableStream({
    async pull(controller) {
      try {
        while (true) {
          // Try to produce output from already-buffered SSE data
          const result = processSSEEvents();
          if (result) {
            controller.enqueue(result);
            return; // Yield control — consumer will pull again
          }

          if (done) {
            // Stream finished — send closing events
            if (textStarted) {
              controller.enqueue(sse({ type: "text-end", id: textId }));
            }
            controller.enqueue(sse({ type: "finish" }));
            controller.enqueue(encoder.encode("data: [DONE]\n\n"));
            controller.close();
            return;
          }

          // Read more data from FastAPI
          const { done: readerDone, value } = await reader.read();
          if (readerDone) {
            done = true;
            // Loop back to process remaining buffer + close
            continue;
          }

          sseBuffer += decoder.decode(value, { stream: true });
          // Loop to process the new data
        }
      } catch (err) {
        controller.error(err);
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "Content-Encoding": "identity",
      Connection: "keep-alive",
      "x-vercel-ai-ui-message-stream": "v1",
      "x-accel-buffering": "no",
    },
  });
}
