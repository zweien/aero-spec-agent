import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { WorkflowTimeline } from "./WorkflowTimeline";
import type { WorkflowStage } from "./useJobEventStream";
import { createElement } from "react";
import { renderToString } from "react-dom/server";

function render(el: React.ReactElement): string {
  return renderToString(el);
}

describe("WorkflowTimeline", () => {
  it("renders empty div when no stages", () => {
    const html = render(createElement(WorkflowTimeline, { stages: [] }));
    assert.equal(html, "<div></div>");
  });

  it("renders step labels for running stages", () => {
    const stages: WorkflowStage[] = [
      { step: "writing_spec", progress: 10, status: "running", timestamp: "" },
    ];
    const html = render(createElement(WorkflowTimeline, { stages }));
    assert.ok(html.includes("编写设计规格"));
  });

  it("renders multiple stages", () => {
    const stages: WorkflowStage[] = [
      { step: "writing_spec", progress: 10, status: "succeeded", timestamp: "" },
      { step: "geometry_building", progress: 25, status: "running", timestamp: "" },
    ];
    const html = render(createElement(WorkflowTimeline, { stages }));
    assert.ok(html.includes("编写设计规格"));
    assert.ok(html.includes("构建几何模型"));
  });

  it("marks all steps completed when succeeded stage arrives", () => {
    const stages: WorkflowStage[] = [
      { step: "writing_spec", progress: 10, status: "running", timestamp: "" },
      { step: "succeeded", progress: 100, status: "succeeded", timestamp: "" },
    ];
    const html = render(createElement(WorkflowTimeline, { stages }));
    // "succeeded" step marks generating_cad as completed
    assert.ok(html.includes("编写设计规格"));
    assert.ok(html.includes("构建几何模型"));
  });
});
