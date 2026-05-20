"use client";

import { type JSX } from "react";

export type AgentRunActionsProps = {
  status: "completed" | "failed";
  designId?: string;
  versionNo?: number;
  isCurrentVersion?: boolean;
  onViewModel?: () => void;
  onDeepDesign?: () => void;
  onExportReport?: () => void;
  onRetry?: () => void;
};

export function AgentRunActions({
  status,
  onViewModel,
  onDeepDesign,
  onExportReport,
  onRetry,
}: AgentRunActionsProps): JSX.Element {
  return (
    <div className="agent-run-actions">
      {status === "completed" && (
        <>
          {onViewModel && (
            <button type="button" className="agent-run-btn" onClick={onViewModel}>
              查看模型
            </button>
          )}
          {onDeepDesign && (
            <button type="button" className="agent-run-btn" onClick={onDeepDesign}>
              深度设计探索
            </button>
          )}
          {onExportReport && (
            <button type="button" className="agent-run-btn" onClick={onExportReport}>
              导出报告
            </button>
          )}
        </>
      )}
      {status === "failed" && (
        <>
          {onRetry && (
            <button type="button" className="agent-run-btn" onClick={onRetry}>
              重试
            </button>
          )}
          <button type="button" className="agent-run-btn">
            查看日志
          </button>
        </>
      )}
    </div>
  );
}
