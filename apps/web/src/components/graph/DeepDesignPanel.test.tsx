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

test("DeepDesignPanel renders input form with stream prop", () => {
  const html = renderToString(
    <DeepDesignPanel apiBaseUrl="http://localhost:3800" stream={mockStream} />,
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
    />,
  );
  assert.ok(html.includes("test"));
});

test("DeepDesignPanel shows no-spec notice when defaultSpec is undefined", () => {
  const html = renderToString(
    <DeepDesignPanel apiBaseUrl="http://localhost:3800" stream={mockStream} />,
  );
  assert.ok(html.includes("请先通过对话生成或加载一个基础设计"));
});

test("DeepDesignPanel shows cancel button only while running", () => {
  const runningStream = { ...mockStream, status: "running" as const };
  const html = renderToString(
    <DeepDesignPanel apiBaseUrl="http://localhost:3800" stream={runningStream} />,
  );
  assert.ok(html.includes("取消"));
});

test("DeepDesignPanel shows report when stream has report", () => {
  const completedStream = { ...mockStream, report: "# Test Report", status: "completed" as const };
  const html = renderToString(
    <DeepDesignPanel apiBaseUrl="http://localhost:3800" stream={completedStream} />,
  );
  assert.ok(html.includes("Test Report"));
});
