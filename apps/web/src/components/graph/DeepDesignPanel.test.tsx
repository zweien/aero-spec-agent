import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToString } from "react-dom/server";

import { DeepDesignPanel } from "./DeepDesignPanel.tsx";

test("DeepDesignPanel renders input form", () => {
  const html = renderToString(<DeepDesignPanel apiBaseUrl="http://localhost:3800" />);
  assert.ok(html.includes("Deep Design Exploration"));
  assert.ok(html.includes("Description"));
  assert.ok(html.includes("Start Exploration"));
});

test("DeepDesignPanel renders with default spec", () => {
  const html = renderToString(
    <DeepDesignPanel
      apiBaseUrl="http://localhost:3800"
      defaultSpec={{ aircraft: { name: "test" } }}
    />,
  );
  assert.ok(html.includes("test"));
});

test("DeepDesignPanel shows cancel button text only while running (via state)", () => {
  // Cancel button is conditionally rendered based on runtime state (isRunning).
  // In SSR, isRunning is always false, so cancel should not appear.
  const html = renderToString(<DeepDesignPanel apiBaseUrl="http://localhost:3800" />);
  assert.ok(!html.includes("Cancel"));
});
