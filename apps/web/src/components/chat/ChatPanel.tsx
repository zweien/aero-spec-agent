"use client";

import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

export type ChatMessage = {
  role: "user" | "assistant" | "error" | "generating";
  content: string;
};

type ChatPanelProps = {
  messages: ChatMessage[];
  isGenerating: boolean;
  onSend: (message: string) => void;
};

export function ChatPanel({ messages, isGenerating, onSend }: ChatPanelProps) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function handleSubmit() {
    const trimmed = input.trim();
    if (!trimmed || isGenerating) return;
    onSend(trimmed);
    setInput("");
  }

  return (
    <section className="panel chat-panel">
      <header>对话</header>
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="message assistant">
            描述你想要的飞机设计，例如「设计一架翼展 12 米、双发、上单翼、常规尾翼的固定翼无人机」。
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            {msg.role === "assistant" ? (
              <Markdown remarkPlugins={[remarkGfm]}>{msg.content}</Markdown>
            ) : (
              msg.content
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
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
          disabled={isGenerating}
        />
        <button type="button" disabled={isGenerating || !input.trim()} onClick={handleSubmit}>
          {isGenerating ? "生成中" : "发送"}
        </button>
      </div>
    </section>
  );
}
