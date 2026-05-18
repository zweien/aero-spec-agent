"use client";

import { useCallback, useRef, useState } from "react";

import {
  type GraphNode,
  type GraphNodeState,
  type StreamEvent,
  type VariantResult,
  type VariantStatus,
} from "./GraphExecutionPanel";

// ---------------------------------------------------------------------------
// SSE types from /api/deep-design/stream
// ---------------------------------------------------------------------------

export type DeepDesignSseEvent = {
  event: string;
  data: Record<string, unknown>;
};

// ---------------------------------------------------------------------------
// Node label mapping
// ---------------------------------------------------------------------------

const NODE_LABELS: Record<string, string> = {
  parse_requirements: "Parse",
  prepare_variants: "Prepare",
  run_compare: "Compare",
  refine_variants: "Refine",
  synthesize_report: "Report",
};

const NODE_ORDER = [
  "parse_requirements",
  "prepare_variants",
  "run_compare",
  "refine_variants",
  "synthesize_report",
];

// ---------------------------------------------------------------------------
// State reducer
// ---------------------------------------------------------------------------

export type DeepDesignStreamState = {
  nodes: GraphNode[];
  variants: VariantResult[];
  events: StreamEvent[];
  status: "idle" | "running" | "completed" | "failed";
  report: string;
};

const INITIAL_STATE: DeepDesignStreamState = {
  nodes: [],
  variants: [],
  events: [],
  status: "idle",
  report: "",
};

function toTimestamp(): string {
  return new Date().toLocaleTimeString("en-US", { hour12: false });
}

function applyEvent(
  prev: DeepDesignStreamState,
  sse: DeepDesignSseEvent,
): DeepDesignStreamState {
  const { event: eventType, data } = sse;
  const next: DeepDesignStreamState = { ...prev, status: "running" };

  // --- graph_node events ---
  if (eventType === "graph_node") {
    const node = data.node as string;
    const nodeStatus = data.status as string;
    const latencyMs = data.latency_ms as number | undefined;

    // Update nodes list
    const existing = next.nodes.find((n) => n.name === node);
    if (existing) {
      existing.state = nodeStatus as GraphNodeState;
      if (latencyMs != null) existing.latencyMs = latencyMs;
    } else {
      next.nodes = [
        ...next.nodes,
        {
          name: node,
          label: NODE_LABELS[node] || node,
          state: nodeStatus as GraphNodeState,
          latencyMs,
        },
      ];
    }

    // Sort by canonical order
    next.nodes = [...next.nodes].sort(
      (a, b) => NODE_ORDER.indexOf(a.name) - NODE_ORDER.indexOf(b.name),
    );

    // Add to event stream
    next.events = [
      ...next.events,
      {
        timestamp: toTimestamp(),
        eventType: `node:${node} ${nodeStatus}`,
        detail: latencyMs != null ? `${latencyMs.toFixed(0)}ms` : undefined,
      },
    ];
  }

  // --- generation_* events (from variant jobs) ---
  if (
    eventType === "generation_started" ||
    eventType === "generation_progress" ||
    eventType === "generation_complete" ||
    eventType === "generation_failed"
  ) {
    const jobId = (data.job_id as string) || "";
    const step = (data.current_step as string) || "";

    // Add to event stream
    next.events = [
      ...next.events,
      {
        timestamp: toTimestamp(),
        eventType,
        jobId: jobId || undefined,
        detail: step || undefined,
      },
    ];

    // Track variant status from generation events
    if (eventType === "generation_started" || eventType === "generation_complete" || eventType === "generation_failed") {
      const label = step || jobId.slice(0, 8) || "variant";
      const existingVariant = next.variants.find((v) => v.jobId === jobId);
      if (existingVariant) {
        if (eventType === "generation_complete") {
          existingVariant.status = "succeeded";
          existingVariant.durationMs = data.duration_ms as number | undefined;
        } else if (eventType === "generation_failed") {
          existingVariant.status = "failed";
        } else {
          existingVariant.status = "running";
        }
      } else if (jobId) {
        const vStatus: VariantStatus =
          eventType === "generation_complete"
            ? "succeeded"
            : eventType === "generation_failed"
              ? "failed"
              : "running";
        next.variants = [
          ...next.variants,
          { label, status: vStatus, jobId, durationMs: data.duration_ms as number | undefined },
        ];
      }
    }
  }

  // --- message events (final result) ---
  if (eventType === "message") {
    const content = data.content as string;
    const msgStatus = data.status as string;
    next.report = content;
    if (msgStatus === "failed") {
      next.status = "failed";
    } else {
      next.status = "completed";
    }

    next.events = [
      ...next.events,
      {
        timestamp: toTimestamp(),
        eventType: "message",
        detail: (msgStatus || "") as string,
      },
    ];
  }

  return next;
}

// ---------------------------------------------------------------------------
// SSE parser
// ---------------------------------------------------------------------------

export function parseSseChunk(chunk: string): DeepDesignSseEvent[] {
  const events: DeepDesignSseEvent[] = [];
  let currentEvent: string | null = null;
  let currentData: string | null = null;

  for (const line of chunk.split("\n")) {
    if (line.startsWith("event: ")) {
      currentEvent = line.slice(7);
    } else if (line.startsWith("data: ")) {
      currentData = line.slice(6);
    } else if (line === "" && currentEvent !== null && currentData !== null) {
      try {
        events.push({
          event: currentEvent,
          data: JSON.parse(currentData),
        });
      } catch {
        // Skip malformed JSON
      }
      currentEvent = null;
      currentData = null;
    }
  }
  return events;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useDeepDesignStream() {
  const [state, setState] = useState<DeepDesignStreamState>(INITIAL_STATE);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(
    async (apiBaseUrl: string, request: {
      design_id: string;
      description: string;
      base_spec: Record<string, unknown>;
      constraints?: Record<string, unknown>;
    }) => {
      // Abort previous run
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setState({ ...INITIAL_STATE, status: "running" });

      try {
        const response = await fetch(`${apiBaseUrl}/api/deep-design/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(request),
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          setState((prev) => ({ ...prev, status: "failed" }));
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Parse complete events from buffer
          const events = parseSseChunk(buffer);
          if (events.length > 0) {
            // Keep incomplete trailing lines in buffer
            const lastDoubleNewline = buffer.lastIndexOf("\n\n");
            if (lastDoubleNewline !== -1) {
              buffer = buffer.slice(lastDoubleNewline + 2);
            }

            setState((prev) => {
              let current = prev;
              for (const event of events) {
                current = applyEvent(current, event);
              }
              return current;
            });
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setState((prev) => ({ ...prev, status: "failed" }));
        }
      }
    },
    [],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
    setState((prev) => ({ ...prev, status: prev.status === "running" ? "idle" : prev.status }));
  }, []);

  return { ...state, start, stop };
}
