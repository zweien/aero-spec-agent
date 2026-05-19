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
    // writing_spec is running (◉), rest are pending (○)
    assert.ok(html.includes("编写设计规格"));
    assert.ok(html.includes("构建几何模型"));
  });

  it("marks earlier steps completed when later step arrives", () => {
    const stages: WorkflowStage[] = [
      { step: "writing_spec", progress: 10, status: "running", timestamp: "" },
      { step: "geometry_building", progress: 25, status: "running", timestamp: "" },
    ];
    const html = render(createElement(WorkflowTimeline, { stages }));
    // writing_spec → completed (●), geometry_building → running (◉)
    assert.ok(html.includes("编写设计规格"));
    assert.ok(html.includes("构建几何模型"));
    // Check that completed icon appears for writing_spec and running for geometry_building
    assert.ok(html.includes("●"));
    assert.ok(html.includes("◉"));
  });

  it("marks all steps completed when succeeded stage arrives", () => {
    const stages: WorkflowStage[] = [
      { step: "writing_spec", progress: 10, status: "running", timestamp: "" },
      { step: "geometry_building", progress: 25, status: "running", timestamp: "" },
      { step: "succeeded", progress: 100, status: "succeeded", timestamp: "" },
    ];
    const html = render(createElement(WorkflowTimeline, { stages }));
    // All ALL_STEPS should be completed (●), no running (◉) or pending (○)
    assert.ok(html.includes("编写设计规格"));
    assert.ok(html.includes("构建几何模型"));
    assert.ok(html.includes("导出三维模型"));
    assert.ok(html.includes("生成分析报告"));
    assert.ok(html.includes("生成 CAD 模型"));
    // No running indicators left
    assert.ok(!html.includes("◉"));
    assert.ok(!html.includes("○"));
  });

  it("shows pending for steps after current", () => {
    const stages: WorkflowStage[] = [
      { step: "writing_spec", progress: 10, status: "running", timestamp: "" },
    ];
    const html = render(createElement(WorkflowTimeline, { stages }));
    // Steps after writing_spec should be pending (○)
    assert.ok(html.includes("○"));
  });
});
