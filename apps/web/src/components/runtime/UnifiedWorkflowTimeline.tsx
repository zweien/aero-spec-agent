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

type StatusColor = "var(--success)" | "var(--accent)" | "var(--error)" | "var(--text-muted)";

const STATUS_COLORS: Record<string, StatusColor> = {
  completed: "var(--success)",
  running: "var(--accent)",
  failed: "var(--error)",
  pending: "var(--text-muted)",
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
    <div style={{ display: "flex", flexDirection: "column", marginTop: "8px" }}>
      {stages.map((item, i) => {
        const isLast = i === stages.length - 1;
        const isRunning = item.status === "running";
        const color = STATUS_COLORS[item.status] ?? "var(--text-muted)";
        const duration = formatDuration(item.durationMs);

        return (
          <div key={item.stage}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span
                style={{
                  color,
                  fontSize: "14px",
                  lineHeight: 1,
                  animation: isRunning ? "pulse 1.5s ease-in-out infinite" : "none",
                }}
              >
                {stageIcon(item.status)}
              </span>
              <span
                style={{
                  fontSize: "13px",
                  color: item.status === "pending" ? "var(--text-muted)" : "var(--text)",
                  flex: 1,
                }}
              >
                {item.label}
              </span>
              {duration && (
                <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                  {duration}
                </span>
              )}
            </div>
            {!isLast && (
              <div
                style={{
                  marginLeft: "6px",
                  borderLeft: "2px solid var(--border-default)",
                  height: "14px",
                }}
              />
            )}
          </div>
        );
      })}
      {elapsedTime != null && elapsedTime > 0 && (
        <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px", paddingLeft: "22px" }}>
          已运行：{formatElapsed(elapsedTime)}
        </div>
      )}
    </div>
  );
}
