import { type NextRequest } from "next/server";

const FASTAPI_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8900";

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
  const messageId = `msg-${Date.now()}`;
  const textId = `text-${Date.now()}`;
  let callCounter = 0;
  let currentToolCallId = "";

  const stream = new ReadableStream({
    async start(controller) {
      controller.enqueue(
        encoder.encode(
          `data: ${JSON.stringify({ type: "start", messageId })}\n\n`,
        ),
      );
      controller.enqueue(
        encoder.encode(
          `data: ${JSON.stringify({ type: "text-start", id: textId })}\n\n`,
        ),
      );

      const reader = fastapiResponse.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          let eventType = "";
          for (const line of lines) {
            if (line.startsWith("event: ")) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                switch (eventType) {
                  case "message": {
                    const delta = String(data.content ?? "");
                    if (delta) {
                      controller.enqueue(
                        encoder.encode(
                          `data: ${JSON.stringify({ type: "text-delta", id: textId, delta })}\n\n`,
                        ),
                      );
                    }
                    break;
                  }
                  case "tool_call": {
                    const toolCallId = `call-${++callCounter}`;
                    currentToolCallId = toolCallId;
                    let args: Record<string, unknown> = {};
                    try {
                      args = JSON.parse(String(data.arguments ?? "{}"));
                    } catch {
                      // keep empty args
                    }
                    controller.enqueue(
                      encoder.encode(
                        `data: ${JSON.stringify({
                          type: "tool-input-available",
                          toolCallId,
                          toolName: String(data.name ?? ""),
                          input: args,
                        })}\n\n`,
                      ),
                    );
                    break;
                  }
                  case "generation_complete": {
                    if (currentToolCallId) {
                      controller.enqueue(
                        encoder.encode(
                          `data: ${JSON.stringify({
                            type: "tool-output-available",
                            toolCallId: currentToolCallId,
                            output: data,
                          })}\n\n`,
                        ),
                      );
                    }
                    break;
                  }
                }
              } catch {
                // skip unparseable lines
              }
              eventType = "";
            }
          }
        }
      } finally {
        controller.enqueue(
          encoder.encode(
            `data: ${JSON.stringify({ type: "text-end", id: textId })}\n\n`,
          ),
        );
        controller.enqueue(
          encoder.encode(
            `data: ${JSON.stringify({ type: "finish" })}\n\n`,
          ),
        );
        controller.enqueue(encoder.encode("data: [DONE]\n\n"));
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "x-vercel-ai-ui-message-stream": "v1",
    },
  });
}
