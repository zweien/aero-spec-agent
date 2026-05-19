"use client";

import React, { type JSX } from "react";

import type { GraphNode, GraphNodeState } from "./GraphExecutionPanel";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type GraphTimelineProps = {
  nodes: GraphNode[];
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATE_COLORS: Record<GraphNodeState, string> = {
  completed: "var(--success)",
  running: "var(--accent)",
  failed: "var(--error)",
  pending: "var(--text-muted)",
};

function circleIcon(state: GraphNodeState): string {
  switch (state) {
    case "completed":
      return "●"; // ●
    case "running":
      return "◉"; // ◉
    case "failed":
      return "✗"; // ✗
    default:
      return "○"; // ○
  }
}

function statusText(node: GraphNode): string {
  switch (node.state) {
    case "completed":
      return `✓ ${node.latencyMs != null ? `${Math.round(node.latencyMs)}ms` : ""}`;
    case "running":
      return "...";
    case "failed":
      return "✗";
    default:
      return "";
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function GraphTimeline({ nodes }: GraphTimelineProps): JSX.Element {
  if (nodes.length === 0) {
    return <div />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      {nodes.map((node, i) => {
        const isLast = i === nodes.length - 1;
        const isRunning = node.state === "running";
        const color = STATE_COLORS[node.state];

        return (
          <div key={node.name}>
            {/* Node row */}
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span
                style={{
                  color,
                  fontSize: "16px",
                  lineHeight: 1,
                  animation: isRunning ? "pulse 1.5s ease-in-out infinite" : "none",
                }}
              >
                {circleIcon(node.state)}
              </span>
              <span style={{ fontSize: "13px", color: "var(--text)" }}>
                {node.label}
              </span>
              <span
                style={{
                  fontSize: "11px",
                  color: node.state === "pending" ? "var(--text-muted)" : color,
                  marginLeft: "auto",
                  whiteSpace: "nowrap",
                }}
              >
                {statusText(node)}
              </span>
            </div>

            {/* Vertical connector */}
            {!isLast && (
              <div
                style={{
                  marginLeft: "7px",
                  borderLeft: "2px solid var(--border-default)",
                  height: "16px",
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
