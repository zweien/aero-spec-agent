import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { extractCompareMetrics } from "./metricExtractors.ts";
import type { CompareItem } from "./types.ts";

/** Realistic spec_echo from a real validation_report */
const REAL_SPEC = {
  schema_version: "0.1",
  aircraft: { name: "Test_UAV", type: "fixed_wing_uav", layout: "conventional" },
  fuselage: {
    length: { unit: "m", source: "inferred", confidence: 0.75, value: 8.0 },
    max_diameter: { unit: "m", source: "inferred", confidence: 0.75, value: 1.2 },
  },
  wing: {
    span: { unit: "m", source: "rule_default", confidence: 0.5, value: 6.0 },
    position: { source: "user", confidence: 1.0, value: "high" },
    root_chord: { unit: "m", source: "rule_default", confidence: 0.5, value: 1.0 },
    tip_chord: { unit: "m", source: "rule_default", confidence: 0.5, value: 0.6 },
    sweep: { unit: "deg", source: "inferred", confidence: 0.7, value: 5.0 },
  },
  tail: { type: { source: "user", confidence: 1.0, value: "conventional" } },
};

const REAL_PERF_ESTIMATES = [
  { estimate_id: "wing_area", value: 4.8, unit: "m²" },
  { estimate_id: "aspect_ratio_perf", value: 7.5 },
  { estimate_id: "ld_cruise", value: 15.21 },
  { estimate_id: "range_est", value: 8509.16, unit: "km" },
  { estimate_id: "endurance_est", value: 17.73, unit: "h" },
  { estimate_id: "wing_loading_mtow", value: 486.11, unit: "kg/m²" },
];

function makeItem(overrides: Partial<CompareItem> = {}): CompareItem {
  return { id: "test-1", designId: "d1", versionNo: 1, source: "version", ...overrides };
}

describe("extractCompareMetrics realistic", () => {
  it("extracts from real spec_echo + performance_estimate", () => {
    const item = makeItem({
      spec: REAL_SPEC,
      validationReport: {
        performance_estimate: { estimates: REAL_PERF_ESTIMATES, summary: {} },
      },
    });
    const m = extractCompareMetrics(item);
    assert.equal(m.wingspan_m, 6);
    assert.equal(m.fuselage_length_m, 8);
    assert.equal(m.wing_area_m2, 4.8);
    assert.equal(m.aspect_ratio, 7.5);
    assert.equal(m.estimated_lift_to_drag, 15.21);
    assert.equal(m.estimated_range_km, 8509.16);
    assert.equal(m.estimated_endurance_h, 17.73);
    assert.equal(m.wing_loading_kg_m2, 486.11);
    assert.equal(m.defaulted_fields_count, 0);
  });

  it("falls back to trapezoidal wing_area when estimate missing", () => {
    const item = makeItem({ spec: REAL_SPEC });
    const m = extractCompareMetrics(item);
    // wing_area = span * (root + tip) / 2 = 6 * 1.6 / 2 = 4.8
    assert.ok(Math.abs(m.wing_area_m2! - 4.8) < 0.001);
    // aspect_ratio = 36 / 4.8 = 7.5
    assert.ok(Math.abs(m.aspect_ratio! - 7.5) < 0.001);
  });

  it("handles missing chords gracefully", () => {
    const specNoChords = {
      ...REAL_SPEC,
      wing: { ...REAL_SPEC.wing },
    };
    delete (specNoChords.wing as Record<string, unknown>).root_chord;
    delete (specNoChords.wing as Record<string, unknown>).tip_chord;

    const item = makeItem({ spec: specNoChords });
    const m = extractCompareMetrics(item);
    assert.equal(m.wing_area_m2, undefined);
    assert.equal(m.aspect_ratio, undefined);
    // L/D should still be estimated from aspect_ratio — but it's undefined too
    assert.equal(m.estimated_lift_to_drag, undefined);
    assert.ok(m.missing_metrics_count >= 4);
  });

  it("handles null defaultedFields (old format)", () => {
    const item = makeItem({
      spec: REAL_SPEC,
      validationReport: {
        performance_estimate: { estimates: REAL_PERF_ESTIMATES, summary: {} },
        defaulted_fields: null as unknown as Record<string, unknown>,
      },
    });
    const m = extractCompareMetrics(item);
    assert.equal(m.defaulted_fields_count, 0);
    assert.equal(m.risk_level, "low");
  });

  it("handles empty item with no data", () => {
    const m = extractCompareMetrics(makeItem());
    assert.equal(m.wingspan_m, undefined);
    assert.equal(m.fuselage_length_m, undefined);
    assert.equal(m.risk_level, "medium");
    assert.ok(m.missing_metrics_count >= 5);
  });

  it("handles Deep Design variant item", () => {
    const item = makeItem({
      id: "dd-v3",
      source: "deep-design-variant",
      name: "长航时方案",
      spec: REAL_SPEC,
      validationReport: {
        performance_estimate: { estimates: REAL_PERF_ESTIMATES, summary: {} },
      },
      defaultedFields: [
        { path: "fuselage.length", label: "机身长度", value: 5.0, unit: "m", reason: "LLM 未提供" },
      ],
    });
    const m = extractCompareMetrics(item);
    assert.equal(m.defaulted_fields_count, 1);
    assert.equal(m.risk_level, "low");
  });

  it("handles Recommended variant item", () => {
    const item = makeItem({
      id: "dd-rec",
      source: "recommended",
      name: "推荐方案",
      spec: REAL_SPEC,
      validationReport: {
        performance_estimate: { estimates: REAL_PERF_ESTIMATES, summary: {} },
      },
    });
    const m = extractCompareMetrics(item);
    assert.equal(m.wingspan_m, 6);
    assert.equal(m.estimated_lift_to_drag, 15.21);
  });

  it("no NaN in output", () => {
    const item = makeItem({
      spec: { wing: { span: { value: 0 } } },
    });
    const m = extractCompareMetrics(item);
    for (const [k, v] of Object.entries(m)) {
      if (typeof v === "number") {
        assert.ok(!Number.isNaN(v), `${k} is NaN`);
      }
    }
  });
});
