import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToString } from "react-dom/server";

import { DeepDesignPanel } from "./DeepDesignPanel.tsx";
import type { DeepDesignStreamState } from "./useDeepDesignStream.ts";

const mockStream: DeepDesignStreamState & { start: () => Promise<void>; stop: () => void } = {
  nodes: [],
  variants: [],
  events: [],
  status: "idle",
  report: "",
  start: async () => {},
  stop: () => {},
};

const onLoadVersion = async () => {};
const onSwitchToParameters = () => {};

test("DeepDesignPanel renders input form with stream prop", () => {
  const html = renderToString(
    <DeepDesignPanel
      apiBaseUrl="http://localhost:3800"
      stream={mockStream}
      designId={null}
      onLoadVersion={onLoadVersion}
      onSwitchToParameters={onSwitchToParameters}
    />,
  );
  assert.ok(html.includes("设计需求描述"));
  assert.ok(html.includes("开始探索"));
});

test("DeepDesignPanel renders with default spec", () => {
  const html = renderToString(
    <DeepDesignPanel
      apiBaseUrl="http://localhost:3800"
      stream={mockStream}
      defaultSpec={{ aircraft: { name: "test" } }}
      designId={null}
      onLoadVersion={onLoadVersion}
      onSwitchToParameters={onSwitchToParameters}
    />,
  );
  // Spec is now hidden behind "高级选项" toggle, so not rendered by default
  assert.ok(html.includes("设计需求描述"));
});

test("DeepDesignPanel shows no-spec notice when defaultSpec is undefined", () => {
  const html = renderToString(
    <DeepDesignPanel
      apiBaseUrl="http://localhost:3800"
      stream={mockStream}
      designId={null}
      onLoadVersion={onLoadVersion}
      onSwitchToParameters={onSwitchToParameters}
    />,
  );
  assert.ok(html.includes("请先生成或加载一个基础设计"));
});

test("DeepDesignPanel shows cancel button only while running", () => {
  const runningStream = { ...mockStream, status: "running" as const };
  const html = renderToString(
    <DeepDesignPanel
      apiBaseUrl="http://localhost:3800"
      stream={runningStream}
      designId={null}
      onLoadVersion={onLoadVersion}
      onSwitchToParameters={onSwitchToParameters}
    />,
  );
  assert.ok(html.includes("取消"));
});

test("DeepDesignPanel shows report with markdown when stream has report", () => {
  const completedStream = { ...mockStream, report: "# Test Report", status: "completed" as const };
  const html = renderToString(
    <DeepDesignPanel
      apiBaseUrl="http://localhost:3800"
      stream={completedStream}
      designId="test-id"
      onLoadVersion={onLoadVersion}
      onSwitchToParameters={onSwitchToParameters}
    />,
  );
  assert.ok(html.includes("Test Report"));
  assert.ok(html.includes("设计探索报告"));
});

test("DeepDesignPanel shows strategy checkboxes and depth radios", () => {
  const html = renderToString(
    <DeepDesignPanel
      apiBaseUrl="http://localhost:3800"
      stream={mockStream}
      designId={null}
      onLoadVersion={onLoadVersion}
      onSwitchToParameters={onSwitchToParameters}
    />,
  );
  assert.ok(html.includes("优化策略"));
  assert.ok(html.includes("长航时优化"));
  assert.ok(html.includes("高速优化"));
  assert.ok(html.includes("载荷优化"));
  assert.ok(html.includes("短距起降"));
  assert.ok(html.includes("探索深度"));
  assert.ok(html.includes("快速探索"));
  assert.ok(html.includes("标准探索"));
  assert.ok(html.includes("深度探索"));
});

test("DeepDesignPanel shows next steps when completed", () => {
  const completedStream = { ...mockStream, status: "completed" as const };
  const html = renderToString(
    <DeepDesignPanel
      apiBaseUrl="http://localhost:3800"
      stream={completedStream}
      designId="test-id"
      onLoadVersion={onLoadVersion}
      onSwitchToParameters={onSwitchToParameters}
    />,
  );
  assert.ok(html.includes("下一步建议"));
});

test("DeepDesignPanel shows running status bar", () => {
  const runningStream = { ...mockStream, status: "running" as const };
  const html = renderToString(
    <DeepDesignPanel
      apiBaseUrl="http://localhost:3800"
      stream={runningStream}
      designId={null}
      onLoadVersion={onLoadVersion}
      onSwitchToParameters={onSwitchToParameters}
    />,
  );
  assert.ok(html.includes("AI 正在探索设计方案"));
});
