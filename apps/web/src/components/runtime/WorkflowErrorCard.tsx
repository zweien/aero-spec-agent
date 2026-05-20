"use client";

import React, { type JSX } from "react";

type WorkflowErrorCardProps = {
  failedStage: string;
  errorMessage: string;
  suggestions?: string[];
  onRetry?: () => void;
  onViewLogs?: () => void;
};

const DEFAULT_SUGGESTIONS = [
  "检查参数范围是否合理",
  "重新生成",
];

export function WorkflowErrorCard({
  failedStage,
  errorMessage,
  suggestions,
  onRetry,
  onViewLogs,
}: WorkflowErrorCardProps): JSX.Element {
  const tips = suggestions ?? DEFAULT_SUGGESTIONS;

  return (
    <div className="workflow-error-card" style={{
      border: "1px solid var(--error)",
      borderRadius: "6px",
      padding: "12px",
      marginTop: "8px",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
        <span style={{ color: "var(--error)", fontSize: "14px" }}>✗</span>
        <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--error)" }}>
          生成失败：{failedStage}
        </span>
      </div>
      <p style={{ fontSize: "12px", color: "var(--text-muted)", margin: "0 0 8px 22px" }}>
        {errorMessage}
      </p>
      {tips.length > 0 && (
        <div style={{ margin: "0 0 8px 22px" }}>
          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>建议：</span>
          <ul style={{ margin: "4px 0 0 0", paddingLeft: "16px", fontSize: "12px", color: "var(--text-muted)" }}>
            {tips.map((tip, i) => (
              <li key={i}>{tip}</li>
            ))}
          </ul>
        </div>
      )}
      <div style={{ display: "flex", gap: "8px", marginLeft: "22px" }}>
        {onRetry && (
          <button
            onClick={onRetry}
            style={{
              fontSize: "12px",
              padding: "4px 12px",
              background: "var(--accent)",
              color: "white",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
            }}
          >
            重试
          </button>
        )}
        {onViewLogs && (
          <button
            onClick={onViewLogs}
            style={{
              fontSize: "12px",
              padding: "4px 12px",
              background: "transparent",
              color: "var(--text-muted)",
              border: "1px solid var(--border-default)",
              borderRadius: "4px",
              cursor: "pointer",
            }}
          >
            查看日志
          </button>
        )}
      </div>
    </div>
  );
}
