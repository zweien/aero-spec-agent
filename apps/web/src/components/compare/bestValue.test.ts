import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { findBestIndices, findBestRisk, isBest } from "./bestValue.ts";
import type { CompareMetrics } from "./types.ts";

describe("findBestIndices", () => {
  it("returns empty for fewer than 2 metrics", () => {
    assert.deepEqual(findBestIndices("estimated_lift_to_drag", [{ estimated_lift_to_drag: 15 }]), []);
  });

  it("highlights highest value for higher-is-better metrics", () => {
    const metrics: CompareMetrics[] = [
      { estimated_lift_to_drag: 15 },
      { estimated_lift_to_drag: 18 },
      { estimated_lift_to_drag: 12 },
    ];
    assert.deepEqual(findBestIndices("estimated_lift_to_drag", metrics), [1]);
  });

  it("highlights lowest value for lower-is-better metrics", () => {
    const metrics: CompareMetrics[] = [
      { defaulted_fields_count: 3 },
      { defaulted_fields_count: 1 },
      { defaulted_fields_count: 5 },
    ];
    assert.deepEqual(findBestIndices("defaulted_fields_count", metrics), [1]);
  });

  it("highlights both on tie", () => {
    const metrics: CompareMetrics[] = [
      { estimated_range_km: 300 },
      { estimated_range_km: 300 },
      { estimated_range_km: 200 },
    ];
    assert.deepEqual(findBestIndices("estimated_range_km", metrics), [0, 1]);
  });

  it("skips undefined values", () => {
    const metrics: CompareMetrics[] = [
      { estimated_lift_to_drag: 15 },
      { estimated_lift_to_drag: undefined },
      { estimated_lift_to_drag: 18 },
    ];
    assert.deepEqual(findBestIndices("estimated_lift_to_drag", metrics), [2]);
  });

  it("returns empty when all values are undefined", () => {
    const metrics: CompareMetrics[] = [
      { estimated_lift_to_drag: undefined },
      { estimated_lift_to_drag: undefined },
    ];
    assert.deepEqual(findBestIndices("estimated_lift_to_drag", metrics), []);
  });

  it("does not highlight non-comparable metrics", () => {
    const metrics: CompareMetrics[] = [
      { wingspan_m: 10 },
      { wingspan_m: 15 },
    ];
    assert.deepEqual(findBestIndices("wingspan_m", metrics), []);
  });
});

describe("findBestRisk", () => {
  it("highlights lowest risk", () => {
    const metrics: CompareMetrics[] = [
      { risk_level: "medium" },
      { risk_level: "low" },
      { risk_level: "high" },
    ];
    assert.deepEqual(findBestRisk(metrics), [1]);
  });

  it("returns empty for fewer than 2 items", () => {
    assert.deepEqual(findBestRisk([{ risk_level: "low" }]), []);
  });
});

describe("isBest", () => {
  it("returns true for the best index", () => {
    const metrics: CompareMetrics[] = [
      { estimated_lift_to_drag: 10 },
      { estimated_lift_to_drag: 20 },
    ];
    assert.equal(isBest("estimated_lift_to_drag", 1, metrics), true);
    assert.equal(isBest("estimated_lift_to_drag", 0, metrics), false);
  });

  it("delegates to findBestRisk for risk_level", () => {
    const metrics: CompareMetrics[] = [
      { risk_level: "medium" },
      { risk_level: "low" },
    ];
    assert.equal(isBest("risk_level", 1, metrics), true);
    assert.equal(isBest("risk_level", 0, metrics), false);
  });
});
