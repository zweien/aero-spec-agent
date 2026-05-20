"use client";

import { type JSX } from "react";

import { buildAgentRunActions } from "./AgentRunActionsModel";

export type AgentRunActionsProps = {
  status: "completed" | "failed";
  designId?: string;
  versionNo?: number;
  isCurrentVersion?: boolean;
  onViewModel?: () => void;
  onDeepDesign?: () => void;
  onExportReport?: () => void;
  onShowDetails?: () => void;
  onRetry?: () => void;
  onViewLogs?: () => void;
};

export function AgentRunActions({
  status,
  onViewModel,
  onDeepDesign,
  onExportReport,
  onShowDetails,
  onRetry,
  onViewLogs,
}: AgentRunActionsProps): JSX.Element {
  const actions = buildAgentRunActions({
    status,
    onViewModel,
    onDeepDesign,
    onExportReport,
    onShowDetails,
    onRetry,
    onViewLogs,
  });

  return (
    <div className="agent-run-actions">
      {actions.map((action) => (
        <button
          key={action.key}
          type="button"
          className="agent-run-btn"
          disabled={action.disabled}
          title={action.disabledReason}
          onClick={action.onClick}
        >
          {action.label}
        </button>
      ))}
    </div>
  );
}
