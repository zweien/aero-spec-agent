import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToString } from "react-dom/server";

import { VariantSummaryCard } from "./VariantSummaryCard.tsx";

const noop = async () => {};
const noopFn = () => {};

test("VariantSummaryCard renders label", () => {
  const html = renderToString(
    <VariantSummaryCard
      label="compact"
      status="succeeded"
      versionNo={1}
      designId="test"
      apiBaseUrl="http://localhost:8900"
      onLoadVersion={noop}
      onSwitchToParameters={noopFn}
    />,
  );
  assert.ok(html.includes("compact"));
});

test("VariantSummaryCard renders status", () => {
  const html = renderToString(
    <VariantSummaryCard
      label="extended"
      status="failed"
      versionNo={2}
      designId="test"
      apiBaseUrl="http://localhost:8900"
      onLoadVersion={noop}
      onSwitchToParameters={noopFn}
    />,
  );
  assert.ok(html.includes("failed"));
});

test("VariantSummaryCard renders set as current button", () => {
  const html = renderToString(
    <VariantSummaryCard
      label="standard"
      status="succeeded"
      versionNo={3}
      designId="test"
      apiBaseUrl="http://localhost:8900"
      onLoadVersion={noop}
      onSwitchToParameters={noopFn}
    />,
  );
  assert.ok(html.includes("设为当前方案"));
});
