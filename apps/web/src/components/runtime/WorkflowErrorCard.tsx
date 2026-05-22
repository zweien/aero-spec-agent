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
    <div className="workflow-error-card runtime-notice status-error">
      <div className="workflow-error-header">
        <span className="workflow-error-icon">✗</span>
        <span className="workflow-error-title">
          生成失败：{failedStage}
        </span>
      </div>
      <p className="workflow-error-copy">
        {errorMessage}
      </p>
      {tips.length > 0 && (
        <div className="workflow-error-suggestions">
          <span className="workflow-error-suggestions-title">建议：</span>
          <ul className="workflow-error-suggestions-list">
            {tips.map((tip, i) => (
              <li key={i}>{tip}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="workflow-error-actions">
        {onRetry && (
          <button
            onClick={onRetry}
            className="workflow-error-retry"
          >
            重试
          </button>
        )}
        {onViewLogs && (
          <button
            onClick={onViewLogs}
            className="workflow-error-logs"
          >
            查看日志
          </button>
        )}
      </div>
    </div>
  );
}
