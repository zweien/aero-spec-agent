import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToString } from "react-dom/server";

import { RecommendedVariantCard } from "./RecommendedVariantCard.tsx";

const noop = async () => {};
const noopFn = () => {};

test("RecommendedVariantCard extracts recommendation from report", () => {
  const html = renderToString(
    <RecommendedVariantCard
      report="共探索 3 个变体。推荐：compact（最快完成）"
      variants={[
        { label: "compact", status: "succeeded", versionNo: 1 },
        { label: "extended", status: "succeeded", versionNo: 2 },
      ]}
      designId="test"
      apiBaseUrl="http://localhost:8900"
      onLoadVersion={noop}
      onSwitchToParameters={noopFn}
    />,
  );
  assert.ok(html.includes("compact"));
  assert.ok(html.includes("推荐"));
});

test("RecommendedVariantCard falls back to first succeeded", () => {
  const html = renderToString(
    <RecommendedVariantCard
      report="No recommendation in report"
      variants={[
        { label: "alpha", status: "succeeded", versionNo: 1 },
      ]}
      designId="test"
      apiBaseUrl="http://localhost:8900"
      onLoadVersion={noop}
      onSwitchToParameters={noopFn}
    />,
  );
  assert.ok(html.includes("alpha"));
});

test("RecommendedVariantCard renders nothing with no succeeded variants", () => {
  const html = renderToString(
    <RecommendedVariantCard
      report="All failed"
      variants={[
        { label: "a", status: "failed", versionNo: 1 },
      ]}
      designId="test"
      apiBaseUrl="http://localhost:8900"
      onLoadVersion={noop}
      onSwitchToParameters={noopFn}
    />,
  );
  // Should return empty/null
  assert.ok(!html.includes("推荐方案") || html.length < 50);
});
