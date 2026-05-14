"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8900";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "error";
  content: string;
  tools?: ToolStatus[];
};

export type ToolStatus = {
  name: string;
  label: string;
  state: "running" | "done";
  versionNo?: number;
  files?: string[];
};

type GenerationCompleteData = {
  status?: string;
  version_no?: number;
  design_id?: string;
  files?: string[];
};

type ChatPanelProps = {
  conversationId: string;
  onGenerationComplete: (data: GenerationCompleteData) => void;
};

let msgCounter = 0;

export function ChatPanel({
  conversationId,
  onGenerationComplete,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const handleSubmit = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;
    setInput("");
    void streamChat(trimmed);
  }, [input, isStreaming, conversationId]);

  const streamChat = useCallback(
    async (message: string) => {
      const userMsg: ChatMessage = {
        id: `msg-${++msgCounter}`,
        role: "user",
        content: message,
      };
      const assistantId = `msg-${++msgCounter}`;
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        tools: [],
      };
      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsStreaming(true);

      try {
        const response = await fetch(`${API_BASE_URL}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            conversation_id: conversationId,
            message,
          }),
        });

        if (!response.ok || !response.body) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

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
                processEvent(eventType, data, assistantId);
              } catch {
                // skip
              }
              eventType = "";
            }
          }
        }
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          {
            id: `msg-${++msgCounter}`,
            role: "error",
            content: err instanceof Error ? err.message : "请求失败",
          },
        ]);
      } finally {
        setIsStreaming(false);
      }
    },
    [conversationId],
  );

  const processEvent = useCallback(
    (
      eventType: string,
      data: Record<string, unknown>,
      assistantId: string,
    ) => {
      switch (eventType) {
        case "message":
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content + String(data.content ?? "") }
                : m,
            ),
          );
          break;
        case "tool_call": {
          const name = String(data.name ?? "");
          const label =
            name === "generate_design"
              ? "生成设计"
              : name === "modify_design"
                ? "修改设计"
                : name;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, tools: [...(m.tools ?? []), { name, label, state: "running" as const }] }
                : m,
            ),
          );
          break;
        }
        case "generation_complete": {
          const genData = data as GenerationCompleteData;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    tools: (m.tools ?? []).map((t) =>
                      t.state === "running"
                        ? {
                            ...t,
                            state: "done" as const,
                            versionNo: genData.version_no,
                            files: genData.files as string[] | undefined,
                          }
                        : t,
                    ),
                  }
                : m,
            ),
          );
          onGenerationComplete(genData);
          break;
        }
        case "error":
          setMessages((prev) => [
            ...prev,
            {
              id: `msg-${++msgCounter}`,
              role: "error",
              content: String(data.content ?? "发生错误"),
            },
          ]);
          break;
      }
    },
    [onGenerationComplete],
  );

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
          <div key={msg.id} className={`chat-bubble chat-bubble-${msg.role}`}>
            <div className="chat-avatar">
              {msg.role === "user" ? "你" : msg.role === "error" ? "!" : "AI"}
            </div>
            <div className="chat-bubble-body">
              {msg.content && (
                <Markdown remarkPlugins={[remarkGfm]}>{msg.content}</Markdown>
              )}
              {msg.tools?.map((tool, i) => (
                <ToolCard key={i} tool={tool} />
              ))}
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
              handleSubmit();
            }
          }}
          disabled={isStreaming}
          rows={2}
        />
        <button
          type="button"
          className={isStreaming ? "btn-streaming" : ""}
          disabled={isStreaming || !input.trim()}
          onClick={handleSubmit}
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

function ToolCard({ tool }: { tool: ToolStatus }) {
  return (
    <div
      className={`tool-card ${tool.state === "running" ? "tool-card-running" : "tool-card-done"}`}
    >
      <div className="tool-card-header">
        {tool.state === "running" ? (
          <span className="spinner" />
        ) : (
          <span className="tool-card-check">&#10003;</span>
        )}
        <span className="tool-card-name">{tool.label}</span>
        {tool.versionNo && (
          <span className="tool-card-version">v{tool.versionNo}</span>
        )}
      </div>
      {tool.state === "done" && tool.files && tool.files.length > 0 && (
        <div className="tool-card-files">
          {tool.files.map((f) => (
            <span key={f} className="tool-card-file">
              {f}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
