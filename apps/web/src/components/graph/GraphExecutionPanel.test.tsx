import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToString } from "react-dom/server";

import {
  GraphExecutionPanel,
  GraphNodeTimeline,
  VariantRuntimeStatus,
  EventStreamViewer,
} from "./GraphExecutionPanel.tsx";

test("GraphNodeTimeline renders all nodes", () => {
  const nodes = [
    { name: "parse", label: "Parse", state: "completed" },
    { name: "prepare", label: "Prepare", state: "running" },
  ];
  const html = renderToString(<GraphNodeTimeline nodes={nodes} />);
  assert.ok(html.includes("Parse"));
  assert.ok(html.includes("Prepare"));
});

test("GraphNodeTimeline shows latency", () => {
  const nodes = [
    { name: "parse", label: "Parse", state: "completed", latencyMs: 12.3 },
  ];
  const html = renderToString(<GraphNodeTimeline nodes={nodes} />);
  assert.ok(html.includes("12ms"));
});

test("GraphNodeTimeline renders empty list", () => {
  const html = renderToString(<GraphNodeTimeline nodes={[]} />);
  assert.ok(html);
});

test("VariantRuntimeStatus renders variant table", () => {
  const variants = [
    { label: "compact", status: "succeeded", durationMs: 1200 },
    { label: "standard", status: "running" },
  ];
  const html = renderToString(<VariantRuntimeStatus variants={variants} />);
  assert.ok(html.includes("compact"));
  assert.ok(html.includes("standard"));
  assert.ok(html.includes("1200ms"));
});

test("VariantRuntimeStatus renders empty", () => {
  const html = renderToString(<VariantRuntimeStatus variants={[]} />);
  assert.ok(html.includes("Variant"));
});

test("EventStreamViewer renders events", () => {
  const events = [
    { timestamp: "12:34:56", eventType: "generation_started", jobId: "abc123def" },
    { timestamp: "12:34:57", eventType: "generation_progress", detail: "step=mesh" },
  ];
  const html = renderToString(<EventStreamViewer events={events} />);
  assert.ok(html.includes("generation_started"));
  assert.ok(html.includes("generation_progress"));
  assert.ok(html.includes("abc123de"));
});

test("EventStreamViewer shows empty state", () => {
  const html = renderToString(<EventStreamViewer events={[]} />);
  assert.ok(html.includes("No events yet"));
});

test("GraphExecutionPanel renders all sections", () => {
  const nodes = [{ name: "parse", label: "Parse", state: "completed" }];
  const variants = [{ label: "v1", status: "succeeded" }];
  const events = [{ timestamp: "12:00:00", eventType: "test" }];
  const html = renderToString(
    <GraphExecutionPanel nodes={nodes} variants={variants} events={events} />,
  );
  assert.ok(html.includes("Graph Execution Runtime"));
  assert.ok(html.includes("Node Timeline"));
  assert.ok(html.includes("Variant Status"));
  assert.ok(html.includes("Event Stream"));
});
