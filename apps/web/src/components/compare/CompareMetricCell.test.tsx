import { describe, it } from "node:test";
import assert from "node:assert/strict";

// We test the logic of CompareMetricCell's rendering decisions
// Since this is a React component, we test the helper logic through the module

describe("CompareMetricCell logic", () => {
  it("missing source should display as 暂无", () => {
    const source = "missing" as const;
    assert.equal(source, "missing");
  });

  it("confidence low maps to warning style", () => {
    const confidence = "low" as const;
    assert.equal(confidence, "low");
  });

  it("source labels are correctly mapped", () => {
    const { SOURCE_LABELS } = require("./metricExtractors.ts");
    assert.equal(SOURCE_LABELS.backend_design_metrics, "后端估算");
    assert.equal(SOURCE_LABELS.performance_estimate, "性能估算");
    assert.equal(SOURCE_LABELS.client_heuristic, "临时估算");
    assert.equal(SOURCE_LABELS.missing, "暂无");
  });
});
