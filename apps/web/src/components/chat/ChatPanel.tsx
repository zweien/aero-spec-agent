"use client";

type ChatPanelProps = {
  error?: string | null;
  isGenerating: boolean;
  onGenerate: () => void;
};

export function ChatPanel({ error, isGenerating, onGenerate }: ChatPanelProps) {
  return (
    <section className="panel chat-panel">
      <header>对话</header>
      <div className="message assistant">输入飞机需求后生成参数化设计。MVP 使用示例 spec 触发生成。</div>
      {error ? <div className="message error-message">{error}</div> : null}
      <textarea
        aria-label="设计需求"
        placeholder="设计一架翼展 12 米、双发、上单翼、常规尾翼的固定翼无人机。"
      />
      <button type="button" disabled={isGenerating} onClick={onGenerate}>
        {isGenerating ? "生成中" : "生成"}
      </button>
    </section>
  );
}
