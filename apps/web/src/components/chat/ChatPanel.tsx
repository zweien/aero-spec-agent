"use client";

import { type JSX, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DefaultChatTransport } from "ai";
import { useChat } from "@ai-sdk/react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { buildVersionFileUrl } from "@/components/cad-viewer/cadPreviewSource";

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
  apiBaseUrl: string;
  onGenerationComplete: (data: GenerationCompleteData) => void;
  registerSendMessage?: (fn: (text: string) => void) => void;
};

const TOOL_LABELS: Record<string, string> = {
  generate_design: "生成设计",
  modify_design: "修改设计",
};

export function ChatPanel({
  conversationId,
  apiBaseUrl,
  onGenerationComplete,
  registerSendMessage,
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
    registerSendMessage?.((text: string) => {
      void sendMessage({ text });
    });
  }, [registerSendMessage, sendMessage]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  useEffect(() => {
    for (const message of messages) {
      for (const part of message.parts ?? []) {
        const toolPart = part as unknown as ToolPart;
        if (
          toolPart.toolCallId &&
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
                  const isLastTextPart =
                    i ===
                    (msg.parts ?? []).findLastIndex(
                      (p) => p.type === "text",
                    );
                  return text ? (
                    <span key={i}>
                      <Markdown remarkPlugins={[remarkGfm]}>
                        {text}
                      </Markdown>
                      {isStreaming &&
                        msg.role === "assistant" &&
                        isLastTextPart &&
                        status === "streaming" && (
                          <span className="streaming-cursor" />
                        )}
                    </span>
                  ) : null;
                }
                if (part.type.startsWith("tool-")) {
                  return (
                    <ToolCard
                      key={i}
                      part={part as unknown as ToolPart}
                      apiBaseUrl={apiBaseUrl}
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

function ToolCard({ part, apiBaseUrl }: { part: ToolPart; apiBaseUrl: string }) {
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

      {!isRunning && result?.files && result.files.length > 0 && result.version_no && (
        <div className="tool-card-files">
          {result.files.map((f: string) => (
            <a
              key={f}
              className="tool-card-file"
              href={buildVersionFileUrl(apiBaseUrl, result.design_id ?? "", result.version_no!, f)}
              target="_blank"
              rel="noreferrer"
            >
              {f}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

const SPEC_FIELD_LABELS: Record<string, string> = {
  name: "名称",
  wing_span: "翼展",
  wing_root_chord: "翼根弦长",
  wing_tip_chord: "翼尖弦长",
  wing_sweep: "后掠角",
  wing_dihedral: "上反角",
  wing_airfoil: "翼型",
  wing_position: "机翼位置",
  fuselage_length: "机长",
  fuselage_diameter: "机身直径",
  engine_count: "发动机",
  engine_position: "发动机位置",
  tail_type: "尾翼类型",
  cruise_speed: "巡航速度",
  payload: "载荷",
  priority: "优先级",
};

const SPEC_FIELD_UNIT: Record<string, string> = {
  wing_span: " m",
  wing_root_chord: " m",
  wing_tip_chord: " m",
  wing_sweep: "°",
  wing_dihedral: "°",
  fuselage_length: " m",
  fuselage_diameter: " m",
  engine_count: "发",
  cruise_speed: " km/h",
  payload: " kg",
};

function SpecSummary({
  args,
  toolName,
}: {
  args: Record<string, unknown>;
  toolName: string;
}): JSX.Element {
  if (toolName === "generate_design") {
    const entries: Array<{ k: string; v: string }> = [];
    for (const [key, val] of Object.entries(args)) {
      const label = SPEC_FIELD_LABELS[key] ?? key;
      const unit = SPEC_FIELD_UNIT[key] ?? "";
      if (val != null) entries.push({ k: label, v: `${val}${unit}` });
    }
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
      field: string;
      value: unknown;
      reason?: string;
    }>;
    return (
      <div className="spec-summary">
        {changes.map((c, i) => (
          <div key={i} className="spec-summary-row">
            <span className="spec-summary-key">
              {SPEC_FIELD_LABELS[c.field] ?? c.field}
            </span>
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
