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
  switch (state) {
    case "completed":
      return "bg-green-500";
    case "running":
      return "bg-blue-500 animate-pulse";
    case "failed":
      return "bg-red-500";
    default:
      return "bg-gray-400";
  }
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
    <div className="flex items-center gap-1 overflow-x-auto pb-2">
      {nodes.map((node, i) => (
        <div key={node.name} className="flex items-center">
          <div
            className={`flex flex-col items-center rounded border px-3 py-2 text-xs ${stateClass(node.state)}`}
            style={{ minWidth: 80 }}
          >
            <span className="font-medium text-white">{node.label}</span>
            <span className="text-white/80">
              {stateLabel(node.state)}
              {node.latencyMs != null ? ` ${node.latencyMs.toFixed(0)}ms` : ""}
            </span>
          </div>
          {i < nodes.length - 1 && (
            <span className="mx-1 text-gray-400">&rarr;</span>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// VariantRuntimeStatus
// ---------------------------------------------------------------------------

function variantStatusColor(status: VariantStatus): string {
  switch (status) {
    case "succeeded":
      return "text-green-600";
    case "running":
      return "text-blue-600 animate-pulse";
    case "failed":
      return "text-red-600";
    case "queued":
      return "text-gray-500";
    default:
      return "text-gray-400";
  }
}

export function VariantRuntimeStatus({
  variants,
}: {
  variants: VariantResult[];
}): JSX.Element {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b text-left text-xs text-gray-500">
          <th className="py-1 pr-4">Variant</th>
          <th className="py-1 pr-4">Status</th>
          <th className="py-1 pr-4">Duration</th>
        </tr>
      </thead>
      <tbody>
        {variants.map((v) => (
          <tr key={v.label} className="border-b border-gray-100">
            <td className="py-1 pr-4 font-medium">{v.label}</td>
            <td className={`py-1 pr-4 ${variantStatusColor(v.status)}`}>
              {v.status}
            </td>
            <td className="py-1 pr-4 text-gray-600">
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
    <div className="max-h-48 overflow-y-auto rounded bg-gray-50 p-2 font-mono text-xs">
      {events.length === 0 && (
        <span className="text-gray-400">No events yet.</span>
      )}
      {events.map((ev, i) => (
        <div key={i} className="py-0.5">
          <span className="text-gray-400">[{ev.timestamp}]</span>{" "}
          <span className="font-medium">{ev.eventType}</span>
          {ev.jobId && (
            <span className="text-gray-500"> job={ev.jobId.slice(0, 8)}</span>
          )}
          {ev.detail && (
            <span className="text-gray-500"> {ev.detail}</span>
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
    <div className="flex flex-col gap-4 rounded-lg border bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-gray-700">
        Graph Execution Runtime
      </h3>

      <section>
        <h4 className="mb-1 text-xs font-medium text-gray-500">
          Node Timeline
        </h4>
        <GraphNodeTimeline nodes={nodes} />
      </section>

      <section>
        <h4 className="mb-1 text-xs font-medium text-gray-500">
          Variant Status
        </h4>
        <VariantRuntimeStatus variants={variants} />
      </section>

      <section>
        <h4 className="mb-1 text-xs font-medium text-gray-500">
          Event Stream
        </h4>
        <EventStreamViewer events={events} />
      </section>
    </div>
  );
}
