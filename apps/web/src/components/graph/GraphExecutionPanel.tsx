"use client";

import React, { type JSX } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type GraphNodeState = "pending" | "running" | "completed" | "failed";

export type GraphNode = {
  name: string;
  label: string;
  state: GraphNodeState;
  latencyMs?: number;
};

export type VariantStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "unknown";

export type VariantResult = {
  label: string;
  status: VariantStatus;
  durationMs?: number;
  jobId?: string;
  threadId?: string;
  versionNo?: number;
};

export type StreamEvent = {
  timestamp: string;
  eventType: string;
  jobId?: string;
  detail?: string;
};

export type GraphExecutionPanelProps = {
  nodes: GraphNode[];
  variants: VariantResult[];
  events: StreamEvent[];
};

// ---------------------------------------------------------------------------
// GraphNodeTimeline
// ---------------------------------------------------------------------------

function stateClass(state: GraphNodeState): string {
  return `graph-node-${state}`;
}

function stateLabel(state: GraphNodeState): string {
  switch (state) {
    case "completed":
      return "✓";
    case "running":
      return "⏳";
    case "failed":
      return "✗";
    default:
      return "○";
  }
}

export function GraphNodeTimeline({ nodes }: { nodes: GraphNode[] }): JSX.Element {
  return (
    <div className="graph-node-timeline">
      {nodes.map((node, i) => (
        <div key={node.name} className="graph-node-step">
          <div
            className={`graph-node-card ${stateClass(node.state)}`}
          >
            <span className="graph-node-label">{node.label}</span>
            <span className="graph-node-meta">
              {stateLabel(node.state)}
              {node.latencyMs != null ? ` ${node.latencyMs.toFixed(0)}ms` : ""}
            </span>
          </div>
          {i < nodes.length - 1 && (
            <span className="graph-node-arrow">&rarr;</span>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// VariantRuntimeStatus
// ---------------------------------------------------------------------------

function variantStatusClass(status: VariantStatus): string {
  return `graph-variant-${status}`;
}

export function VariantRuntimeStatus({
  variants,
}: {
  variants: VariantResult[];
}): JSX.Element {
  return (
    <table className="graph-variant-table">
      <thead>
        <tr>
          <th>Variant</th>
          <th>Status</th>
          <th>Duration</th>
        </tr>
      </thead>
      <tbody>
        {variants.map((v) => (
          <tr key={v.label}>
            <td className="graph-variant-label">{v.label}</td>
            <td className={variantStatusClass(v.status)}>
              {v.status}
            </td>
            <td className="graph-variant-duration">
              {v.durationMs != null ? `${v.durationMs.toFixed(0)}ms` : "-"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ---------------------------------------------------------------------------
// EventStreamViewer
// ---------------------------------------------------------------------------

export function EventStreamViewer({
  events,
}: {
  events: StreamEvent[];
}): JSX.Element {
  return (
    <div className="graph-event-stream">
      {events.length === 0 && (
        <span className="graph-event-empty">No events yet.</span>
      )}
      {events.map((ev, i) => (
        <div key={i} className="graph-event-row">
          <span className="graph-event-time">[{ev.timestamp}]</span>{" "}
          <span className="graph-event-type">{ev.eventType}</span>
          {ev.jobId && (
            <span className="graph-event-detail"> job={ev.jobId.slice(0, 8)}</span>
          )}
          {ev.detail && (
            <span className="graph-event-detail"> {ev.detail}</span>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// GraphExecutionPanel (composite)
// ---------------------------------------------------------------------------

export function GraphExecutionPanel({
  nodes,
  variants,
  events,
}: GraphExecutionPanelProps): JSX.Element {
  return (
    <div className="panel graph-execution-panel">
      <h3 className="graph-execution-title">
        Graph Execution Runtime
      </h3>

      <section className="graph-execution-section">
        <h4 className="graph-execution-heading">
          Node Timeline
        </h4>
        <GraphNodeTimeline nodes={nodes} />
      </section>

      <section className="graph-execution-section">
        <h4 className="graph-execution-heading">
          Variant Status
        </h4>
        <VariantRuntimeStatus variants={variants} />
      </section>

      <section className="graph-execution-section">
        <h4 className="graph-execution-heading">
          Event Stream
        </h4>
        <EventStreamViewer events={events} />
      </section>
    </div>
  );
}
