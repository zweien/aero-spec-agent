import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { extractCompareMetrics, SOURCE_LABELS } from "./metricExtractors.ts";
import type { CompareItem, CompareMetricSource } from "./types.ts";

function makeItem(overrides: Partial<CompareItem> = {}): CompareItem {
  return {
    id: "test-1",
    designId: "d1",
    versionNo: 1,
    source: "version",
    ...overrides,
  };
}

describe("metric_sources", () => {
  it("marks backend_design_metrics when value comes from design_metrics", () => {
    const item = makeItem({
      validationReport: {
        design_metrics: {
          wingspan_m: 12,
          wing_area_m2: 16,
          aspect_ratio: 9,
        },
      },
    });
    const m = extractCompareMetrics(item);
    assert.equal(m.metric_sources?.wingspan_m, "backend_design_metrics");
    assert.equal(m.metric_sources?.wing_area_m2, "backend_design_metrics");
    assert.equal(m.metric_sources?.aspect_ratio, "backend_design_metrics");
  });

  it("marks performance_estimate when value comes from perf estimates", () => {
    const item = makeItem({
      validationReport: {
        performance_estimate: {
          estimates: [
            { estimate_id: "ld_cruise", value: 16 },
            { estimate_id: "range_est", value: 3500 },
          ],
        },
      },
    });
    const m = extractCompareMetrics(item);
    assert.equal(m.metric_sources?.estimated_lift_to_drag, "performance_estimate");
    assert.equal(m.metric_sources?.estimated_range_km, "performance_estimate");
  });

  it("marks client_heuristic when computed client-side", () => {
    const item = makeItem({
      spec: {
        wing: { span: { value: 10 }, root_chord: { value: 1.2 }, tip_chord: { value: 0.6 } },
      },
    });
    const m = extractCompareMetrics(item);
    assert.equal(m.metric_sources?.wingspan_m, "client_heuristic");
    assert.equal(m.metric_sources?.wing_area_m2, "client_heuristic");
    assert.equal(m.metric_sources?.aspect_ratio, "client_heuristic");
    assert.equal(m.metric_sources?.estimated_lift_to_drag, "client_heuristic");
  });

  it("marks missing when no value available", () => {
    const m = extractCompareMetrics(makeItem());
    assert.equal(m.metric_sources?.estimated_range_km, "missing");
    assert.equal(m.metric_sources?.estimated_endurance_h, "missing");
    assert.equal(m.metric_sources?.wing_loading_kg_m2, "missing");
  });

  it("sets confidence to high when most metrics from backend", () => {
    const item = makeItem({
      validationReport: {
        design_metrics: {
          wingspan_m: 12,
          fuselage_length_m: 8,
          wing_area_m2: 16,
          aspect_ratio: 9,
          estimated_lift_to_drag: 15,
          estimated_range_km: 3500,
          estimated_endurance_h: 20,
          wing_loading_kg_m2: 28,
        },
      },
    });
    const m = extractCompareMetrics(item);
    assert.equal(m.confidence, "high");
  });

  it("sets confidence to low when most metrics missing", () => {
    const m = extractCompareMetrics(makeItem());
    assert.equal(m.confidence, "low");
  });

  it("populates warnings for missing metrics", () => {
    const m = extractCompareMetrics(makeItem());
    assert.ok(m.warnings && m.warnings.length > 0);
    assert.ok(m.warnings!.some((w) => w.includes("核心指标缺失")));
  });

  it("SOURCE_LABELS has entries for all source types", () => {
    const sources: CompareMetricSource[] = [
      "backend_design_metrics",
      "performance_estimate",
      "client_heuristic",
      "missing",
    ];
    for (const s of sources) {
      assert.ok(SOURCE_LABELS[s], `Missing label for ${s}`);
    }
  });
});
