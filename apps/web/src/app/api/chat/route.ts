import { type NextRequest } from "next/server";
import {
  streamText,
  convertToModelMessages,
  stepCountIs,
  type UIMessage,
} from "ai";
import { createOpenAI } from "@ai-sdk/openai";

import { buildSystemPrompt } from "@/lib/systemPrompt";
import { createChatTools } from "@/lib/chatTools";

const FASTAPI_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8900";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const {
    messages,
    conversation_id,
    selected_refs,
    llm_settings,
    mode,
  }: {
    messages: UIMessage[];
    conversation_id: string;
    selected_refs?: string[];
    llm_settings?: { modelName?: string; apiKey?: string; baseUrl?: string };
    mode?: string;
  } = body;

  // Legacy mode: proxy to FastAPI as before
  if (mode === "legacy") {
    return legacyProxy(body);
  }

  // --- AI SDK mode ---

  // 1. Resolve LLM config
  const modelName =
    llm_settings?.modelName ||
    process.env.OPENAI_MODEL ||
    "gpt-4o";
  const apiKey =
    llm_settings?.apiKey || process.env.OPENAI_API_KEY || "";
  const baseUrl =
    llm_settings?.baseUrl ||
    process.env.OPENAI_BASE_URL ||
    "https://api.openai.com/v1";

  if (!apiKey) {
    return new Response(
      JSON.stringify({ error: "No API key configured" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  // 2. Fetch conversation state from FastAPI for system prompt
  let specYaml: string | null = null;
  try {
    const stateResp = await fetch(
      `${FASTAPI_BASE_URL}/api/conversations/${encodeURIComponent(conversation_id)}/state`,
    );
    if (stateResp.ok) {
      const state = await stateResp.json();
      specYaml = state.current_spec_yaml ?? null;
    }
  } catch {
    // FastAPI unavailable — proceed without spec context
  }

  const systemPrompt = buildSystemPrompt(specYaml, selected_refs ?? []);

  // 3. Create OpenAI-compatible provider
  const openai = createOpenAI({
    apiKey,
    baseURL: baseUrl,
  });

  // 4. Create tools bound to this conversation
  const tools = createChatTools(conversation_id);

  // 5. Stream with AI SDK
  const result = streamText({
    model: openai(modelName),
    system: systemPrompt,
    messages: await convertToModelMessages(messages),
    tools,
    stopWhen: stepCountIs(5),
  });

  return result.toUIMessageStreamResponse();
}

// --- Legacy proxy (original implementation) ---

const TOOL_LABELS: Record<string, string> = {
  generate_design: "生成设计",
  modify_design: "修改设计",
};

let globalToolCallCounter = 1;

async function legacyProxy(body: Record<string, unknown>) {
  const messages = (body.messages ?? []) as Array<{
    role: string;
    content?: string;
    parts?: Array<{ type: string; text?: string }>;
  }>;
  const conversationId = String(body.conversation_id ?? "default");

  const lastUserMsg = [...messages]
    .reverse()
    .find((m) => m.role === "user");
  if (!lastUserMsg) {
    return new Response("No user message", { status: 400 });
  }

  const userText: string =
    typeof lastUserMsg.content === "string"
      ? lastUserMsg.content
      : (lastUserMsg.parts ?? [])
          .filter((p) => p.type === "text")
          .map((p) => p.text ?? "")
          .join("") || "";

  const fastapiResponse = await fetch(`${FASTAPI_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      conversation_id: conversationId,
      message: userText,
      selected_refs: body.selected_refs ?? [],
    }),
  });

  if (!fastapiResponse.ok || !fastapiResponse.body) {
    return new Response("Backend error", {
      status: fastapiResponse.status,
    });
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
    const lines = sseBuffer.split("\n");
    sseBuffer = "";
    let eventType = "";

    for (const line of lines) {
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
              if (delta) output.push(writeTextDelta(delta));
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
              // Pass job_id to frontend so it can stream sub-stage events
              if (data.job_id) {
                output.push(
                  sse({
                    type: "generation-started",
                    job_id: data.job_id,
                    design_id: data.design_id,
                  }),
                );
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

      if (line === "") {
        eventType = "";
        continue;
      }

      sseBuffer = line;
    }

    if (output.length === 0) return null;
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
          const result = processSSEEvents();
          if (result) {
            controller.enqueue(result);
            return;
          }

          if (done) {
            if (textStarted) {
              controller.enqueue(sse({ type: "text-end", id: textId }));
            }
            controller.enqueue(sse({ type: "finish" }));
            controller.enqueue(
              encoder.encode("data: [DONE]\n\n"),
            );
            controller.close();
            return;
          }

          const { done: readerDone, value } = await reader.read();
          if (readerDone) {
            done = true;
            continue;
          }

          sseBuffer += decoder.decode(value, { stream: true });
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
