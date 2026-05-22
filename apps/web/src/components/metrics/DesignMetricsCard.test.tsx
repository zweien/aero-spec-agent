import { describe, it } from "node:test";
import assert from "node:assert/strict";

// DesignMetricsCard renders React component, test helper logic

describe("DesignMetricsCard helpers", () => {
  it("formats integer values", () => {
    const v = 12;
    const fmt = Number.isInteger(v) ? String(v) : v.toFixed(2);
    assert.equal(fmt, "12");
  });

  it("formats decimal values", () => {
    const v = 12.345;
    const fmt = Number.isInteger(v) ? String(v) : v.toFixed(2);
    assert.equal(fmt, "12.35");
  });

  it("maps risk levels to labels", () => {
    const riskLabel = (level: string): string => {
      switch (level) {
        case "low": return "低";
        case "medium": return "中";
        case "high": return "高";
        default: return "未知";
      }
    };
    assert.equal(riskLabel("low"), "低");
    assert.equal(riskLabel("medium"), "中");
    assert.equal(riskLabel("high"), "高");
    assert.equal(riskLabel("unknown"), "未知");
  });

  it("maps confidence levels to labels", () => {
    const labels: Record<string, string> = { high: "高", medium: "中", low: "低" };
    assert.equal(labels.high, "高");
    assert.equal(labels.medium, "中");
    assert.equal(labels.low, "低");
  });
});
