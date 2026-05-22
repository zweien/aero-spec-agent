"use client";

import { type JSX, useState } from "react";

const TOOL_LABELS: Record<string, string> = {
  generate_design: "生成设计",
  modify_design: "修改设计",
  modify_selected_part: "修改选中部件",
};

export type FallbackToolNoticeProps = {
  toolName: string;
  confidence: number;
};

export function FallbackToolNotice({ toolName, confidence }: FallbackToolNoticeProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const label = TOOL_LABELS[toolName] ?? toolName;
  const pct = (confidence * 100).toFixed(0);

  return (
    <div style={{
      border: "1px solid var(--border-info, #3b82f6)",
      borderRadius: "var(--radius-sm, 6px)",
      padding: "6px 10px",
      marginTop: 6,
      background: "rgba(59, 130, 246, 0.04)",
    }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          background: "none", border: "none", cursor: "pointer",
          fontSize: 12, color: "var(--text-muted)", padding: 0,
          display: "flex", alignItems: "center", gap: 4,
          width: "100%", textAlign: "left",
        }}
      >
        <span style={{ color: "var(--border-info, #3b82f6)", fontSize: 12 }}>&#9432;</span>
        模型未调用工具，系统自动识别并执行
        <span style={{ fontSize: 10, marginLeft: "auto" }}>{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "6px 0 0 0", lineHeight: 1.5 }}>
          当前模型未原生支持工具调用（function calling）。系统通过规则引擎识别用户意图，
          并自动映射为「{label}」操作。置信度: {pct}%。
        </p>
      )}
    </div>
  );
}

export const FALLBACK_TOOL_LABELS = TOOL_LABELS;
