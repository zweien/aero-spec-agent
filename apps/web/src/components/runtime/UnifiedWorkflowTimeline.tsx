"use client";

import React, { type JSX } from "react";
import type { WorkflowRuntimeStage } from "@/hooks/useWorkflowRuntime";

// ---------------------------------------------------------------------------
// GraphNode types (mirrored from graph/GraphExecutionPanel for zero-coupling)
// ---------------------------------------------------------------------------

export type GraphNodeState = "pending" | "running" | "completed" | "failed";

export type GraphNode = {
  name: string;
  label: string;
  state: GraphNodeState;
  latencyMs?: number;
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export type UnifiedTimelineMode = "normal" | "deep-design";

export type UnifiedWorkflowTimelineProps = {
  /** Workflow stages from useWorkflowRuntime (normal mode) */
  stages?: WorkflowRuntimeStage[];
  /** Graph nodes from deep design stream (deep-design mode) */
  nodes?: GraphNode[];
  mode?: UnifiedTimelineMode;
  elapsedTime?: number;
};

const STATUS_CLASSES: Record<string, string> = {
  completed: "workflow-stage-completed status-success",
  running: "workflow-stage-running status-running",
  failed: "workflow-stage-failed status-error",
  pending: "workflow-stage-pending",
};

function stageIcon(status: string): string {
  switch (status) {
    case "completed": return "●";
    case "running": return "⟳";
    case "failed": return "✗";
    default: return "□";
  }
}

function formatDuration(ms: number | null): string {
  if (ms === null || ms === 0) return "";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatElapsed(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

// ---------------------------------------------------------------------------
// Convert GraphNode[] to WorkflowRuntimeStage[]
// ---------------------------------------------------------------------------

export function nodesToStages(nodes: GraphNode[]): WorkflowRuntimeStage[] {
  return nodes.map((n) => ({
    stage: n.name,
    label: n.label,
    status: n.state as WorkflowRuntimeStage["status"],
    startedAt: null,
    completedAt: null,
    durationMs: n.latencyMs ?? null,
  }));
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function UnifiedWorkflowTimeline({ stages: stagesProp, nodes, mode = "normal", elapsedTime }: UnifiedWorkflowTimelineProps): JSX.Element {
  // Resolve effective stages: prefer explicit stages, fall back to GraphNode conversion
  const stages = (stagesProp && stagesProp.length > 0)
    ? stagesProp
    : nodes && nodes.length > 0
      ? nodesToStages(nodes)
      : [];

  if (stages.length === 0) return <div />;

  return (
    <div className={`workflow-timeline workflow-timeline-${mode}`}>
      {stages.map((item, i) => {
        const isLast = i === stages.length - 1;
        const duration = formatDuration(item.durationMs);
        const statusClass = STATUS_CLASSES[item.status] ?? "workflow-stage-pending";

        return (
          <div key={item.stage} className={`workflow-stage ${statusClass}`}>
            <div className="workflow-stage-row">
              <span className="workflow-stage-indicator">
                {stageIcon(item.status)}
              </span>
              <span className="workflow-stage-label">
                {item.label}
              </span>
              {duration && (
                <span className="workflow-stage-duration">
                  {duration}
                </span>
              )}
            </div>
            {!isLast && (
              <div className="workflow-stage-rail" />
            )}
          </div>
        );
      })}
      {elapsedTime != null && elapsedTime > 0 && (
        <div className="workflow-elapsed-time">
          已运行：{formatElapsed(elapsedTime)}
        </div>
      )}
    </div>
  );
}
