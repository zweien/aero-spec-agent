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
    <div className="runtime-notice runtime-notice-info">
      <button
        onClick={() => setOpen(!open)}
        className="runtime-notice-toggle"
      >
        <span className="runtime-notice-icon">&#9432;</span>
        模型未调用工具，系统自动识别并执行
        <span className="runtime-notice-caret">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <p className="runtime-notice-copy">
          当前模型未原生支持工具调用（function calling）。系统通过规则引擎识别用户意图，
          并自动映射为「{label}」操作。置信度: {pct}%。
        </p>
      )}
    </div>
  );
}

export const FALLBACK_TOOL_LABELS = TOOL_LABELS;
