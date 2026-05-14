"use client";

import { type JSX, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DefaultChatTransport } from "ai";
import { useChat } from "@ai-sdk/react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

export type GenerationCompleteData = {
  status?: string;
  version_no?: number;
  design_id?: string;
  files?: string[];
};

type ToolPart = {
  type: string;
  toolCallId: string;
  toolName: string;
  args?: Record<string, unknown>;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  result?: Record<string, unknown>;
  state: string;
};

type ChatPanelProps = {
  conversationId: string;
  onGenerationComplete: (data: GenerationCompleteData) => void;
};

const TOOL_LABELS: Record<string, string> = {
  generate_design: "生成设计",
  modify_design: "修改设计",
};

export function ChatPanel({
  conversationId,
  onGenerationComplete,
}: ChatPanelProps) {
  const [input, setInput] = useState("");
  const processedCalls = useRef(new Set<string>());
  const scrollRef = useRef<HTMLDivElement>(null);

  const transport = useMemo(
    () =>
      new DefaultChatTransport({
        body: { conversation_id: conversationId },
      }),
    [conversationId],
  );

  const { messages, sendMessage, status } = useChat({ transport });

  const isStreaming = status === "streaming" || status === "submitted";

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  useEffect(() => {
    for (const message of messages) {
      for (const part of message.parts ?? []) {
        if (
          part.type.startsWith("tool-") &&
          "state" in part &&
          "toolCallId" in part
        ) {
          const toolPart = part as unknown as ToolPart;
          if (
            toolPart.state === "output-available" &&
            !processedCalls.current.has(toolPart.toolCallId)
          ) {
            processedCalls.current.add(toolPart.toolCallId);
            const output = (toolPart.output ?? toolPart.result) as
              | GenerationCompleteData
              | undefined;
            if (output) {
              onGenerationComplete(output);
            }
          }
        }
      }
    }
  }, [messages, onGenerationComplete]);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;
    setInput("");
    void sendMessage({ text: trimmed });
  }, [input, isStreaming, sendMessage]);

  return (
    <section className="panel chat-panel">
      <header>对话</header>
      <div className="chat-messages" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="chat-empty-icon">&#9992;</div>
            <p>
              描述你想要的飞机设计，例如「设计一架翼展 12
              米、双发、上单翼、常规尾翼的固定翼无人机」。
            </p>
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`chat-bubble chat-bubble-${msg.role}`}
          >
            <div className="chat-avatar">
              {msg.role === "user" ? "你" : "AI"}
            </div>
            <div className="chat-bubble-body">
              {(msg.parts ?? []).map((part, i) => {
                if (part.type === "text") {
                  const text = (part as { type: "text"; text: string }).text;
                  return text ? (
                    <Markdown key={i} remarkPlugins={[remarkGfm]}>
                      {text}
                    </Markdown>
                  ) : null;
                }
                if (part.type.startsWith("tool-")) {
                  return (
                    <ToolCard
                      key={i}
                      part={part as unknown as ToolPart}
                    />
                  );
                }
                return null;
              })}
            </div>
          </div>
        ))}
      </div>
      <div className="chat-input-row">
        <textarea
          aria-label="设计需求"
          placeholder="描述飞机设计需求..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          disabled={isStreaming}
          rows={2}
        />
        <button
          type="button"
          className={isStreaming ? "btn-streaming" : ""}
          disabled={isStreaming || !input.trim()}
          onClick={handleSend}
        >
          {isStreaming ? (
            <>
              <span className="spinner" /> 生成中
            </>
          ) : (
            "发送"
          )}
        </button>
      </div>
    </section>
  );
}

function ToolCard({ part }: { part: ToolPart }) {
  const [expanded, setExpanded] = useState(false);
  const toolName = part.toolName || part.type.replace(/^tool-/, "");
  const label = TOOL_LABELS[toolName] ?? toolName;
  const isRunning =
    part.state === "input-streaming" ||
    part.state === "input-available" ||
    part.state === "call";
  const result = (part.output ?? part.result) as GenerationCompleteData | undefined;

  return (
    <div
      className={`tool-card ${isRunning ? "tool-card-running" : "tool-card-done"}`}
    >
      <div className="tool-card-header">
        {isRunning ? (
          <span className="spinner" />
        ) : (
          <span className="tool-card-check">&#10003;</span>
        )}
        <span className="tool-card-name">{label}</span>
        {result?.version_no && (
          <span className="tool-card-version">v{result.version_no}</span>
        )}
      </div>

      {(part.args ?? part.input) && (
        <button
          type="button"
          className="tool-card-toggle"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? "▾ 收起参数" : "▸ 查看参数"}
        </button>
      )}
      {expanded && (part.args ?? part.input) && (
        <div className="tool-card-args">
          <SpecSummary args={(part.args ?? part.input)!} toolName={toolName} />
        </div>
      )}

      {!isRunning && result?.files && result.files.length > 0 && (
        <div className="tool-card-files">
          {result.files.map((f: string) => (
            <span key={f} className="tool-card-file">
              {f}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function SpecSummary({
  args,
  toolName,
}: {
  args: Record<string, unknown>;
  toolName: string;
}): JSX.Element {
  if (toolName === "generate_design") {
    const aircraft = (args.aircraft ?? {}) as Record<string, unknown>;
    const wing = (args.wing ?? {}) as Record<string, unknown>;
    const fuselage = (args.fuselage ?? {}) as Record<string, unknown>;
    const engine = (args.engine ?? {}) as Record<string, unknown>;
    const entries: Array<{ k: string; v: string }> = [];
    if ("name" in aircraft)
      entries.push({ k: "名称", v: String(aircraft.name) });
    const wingSpan = wing.span as Record<string, unknown> | undefined;
    if (wingSpan)
      entries.push({
        k: "翼展",
        v: `${wingSpan.value} ${wingSpan.unit ?? "m"}`,
      });
    const fuseLen = fuselage.length as Record<string, unknown> | undefined;
    if (fuseLen)
      entries.push({
        k: "机长",
        v: `${fuseLen.value} ${fuseLen.unit ?? "m"}`,
      });
    const wingPos = wing.position as Record<string, unknown> | undefined;
    if (wingPos) entries.push({ k: "机翼位置", v: String(wingPos.value) });
    const engCount = engine.count as Record<string, unknown> | undefined;
    if (engCount) entries.push({ k: "发动机", v: `${engCount.value}发` });
    return (
      <div className="spec-summary">
        {entries.map((e) => (
          <div key={e.k} className="spec-summary-row">
            <span className="spec-summary-key">{e.k}</span>
            <span className="spec-summary-val">{e.v}</span>
          </div>
        ))}
      </div>
    );
  }

  if (toolName === "modify_design") {
    const changes = (args.changes ?? []) as Array<{
      path: string;
      value: unknown;
      reason?: string;
    }>;
    return (
      <div className="spec-summary">
        {changes.map((c, i) => (
          <div key={i} className="spec-summary-row">
            <span className="spec-summary-key">{c.path}</span>
            <span className="spec-summary-val">
              {JSON.stringify(c.value)}
            </span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <pre className="spec-summary-raw">
      {JSON.stringify(args, null, 2)}
    </pre>
  );
}
