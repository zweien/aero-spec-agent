import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToString } from "react-dom/server";

import { GraphTimeline } from "./GraphTimeline.tsx";
import type { GraphNode } from "./GraphExecutionPanel.tsx";

test("GraphTimeline renders empty with no nodes", () => {
  const html = renderToString(<GraphTimeline nodes={[]} />);
  // Should render something (not throw)
  assert.ok(html.length > 0);
});

test("GraphTimeline renders Chinese labels", () => {
  const nodes: GraphNode[] = [
    { name: "parse_requirements", label: "解析设计目标", state: "completed", latencyMs: 1 },
    { name: "synthesize_report", label: "生成设计建议", state: "pending" },
  ];
  const html = renderToString(<GraphTimeline nodes={nodes} />);
  assert.ok(html.includes("解析设计目标"));
  assert.ok(html.includes("生成设计建议"));
});

test("GraphTimeline shows completed status", () => {
  const nodes: GraphNode[] = [
    { name: "parse_requirements", label: "解析设计目标", state: "completed", latencyMs: 5 },
  ];
  const html = renderToString(<GraphTimeline nodes={nodes} />);
  assert.ok(html.includes("5"));
});

test("GraphTimeline shows running state", () => {
  const nodes: GraphNode[] = [
    { name: "run_compare", label: "分析方案差异", state: "running" },
  ];
  const html = renderToString(<GraphTimeline nodes={nodes} />);
  assert.ok(html.includes("分析方案差异"));
});
