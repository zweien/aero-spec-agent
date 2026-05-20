import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { extractCompareMetrics } from "./metricExtractors.ts";
import type { CompareItem } from "./types.ts";

function makeItem(overrides: Partial<CompareItem> = {}): CompareItem {
  return {
    id: "test-1",
    designId: "d1",
    versionNo: 1,
    source: "version",
    ...overrides,
  };
}

describe("extractCompareMetrics", () => {
  it("extracts wingspan from spec.wing.span.value", () => {
    const item = makeItem({
      spec: { wing: { span: { value: 12, unit: "m" } } },
    });
    const m = extractCompareMetrics(item);
    assert.equal(m.wingspan_m, 12);
  });

  it("extracts wingspan from spec.wing.span (number)", () => {
    const item = makeItem({
      spec: { wing: { span: 10 } },
    });
    const m = extractCompareMetrics(item);
    assert.equal(m.wingspan_m, 10);
  });

  it("extracts fuselage_length_m from spec.fuselage.length.value", () => {
    const item = makeItem({
      spec: { fuselage: { length: { value: 6.5 } } },
    });
    const m = extractCompareMetrics(item);
    assert.equal(m.fuselage_length_m, 6.5);
  });

  it("estimates wing_area from span and chords", () => {
    const item = makeItem({
      spec: {
        wing: { span: { value: 10 }, root_chord: { value: 1.5 }, tip_chord: { value: 0.8 } },
      },
    });
    const m = extractCompareMetrics(item);
    // wing_area = span * (root + tip) / 2 = 10 * 2.3 / 2 = 11.5
    assert.equal(m.wing_area_m2, 11.5);
    // aspect_ratio = span^2 / area = 100 / 11.5 ≈ 8.696
    assert.ok(m.aspect_ratio != null);
    assert.ok(Math.abs(m.aspect_ratio! - 8.695) < 0.01);
  });

  it("extracts from performance_estimate estimates", () => {
    const item = makeItem({
      validationReport: {
        performance_estimate: {
          estimates: [
            { estimate_id: "ld_cruise", value: 16.5 },
            { estimate_id: "range_est", value: 350 },
            { estimate_id: "wing_loading_mtow", value: 85.2 },
          ],
        },
      },
    });
    const m = extractCompareMetrics(item);
    assert.equal(m.estimated_lift_to_drag, 16.5);
    assert.equal(m.estimated_range_km, 350);
    assert.equal(m.wing_loading_kg_m2, 85.2);
  });

  it("counts defaulted_fields_count", () => {
    const item = makeItem({
      defaultedFields: [
        { path: "fuselage.length", label: "机身长度", value: 5.0, unit: "m", reason: "test" },
        { path: "wing.position", label: "机翼位置", value: "mid", reason: "test" },
      ],
    });
    const m = extractCompareMetrics(item);
    assert.equal(m.defaulted_fields_count, 2);
  });

  it("sets risk_level to medium when defaulted_fields >= 5", () => {
    const item = makeItem({
      defaultedFields: Array.from({ length: 6 }, (_, i) => ({
        path: `field.${i}`,
        label: `Field ${i}`,
        value: i,
        reason: "test",
      })),
    });
    const m = extractCompareMetrics(item);
    assert.equal(m.risk_level, "medium");
  });

  it("estimates lift_to_drag from aspect_ratio when no direct value", () => {
    const item = makeItem({
      spec: { wing: { span: { value: 10 }, root_chord: { value: 1.2 }, tip_chord: { value: 0.6 } } },
    });
    const m = extractCompareMetrics(item);
    // wing_area = 10 * 1.8 / 2 = 9, aspect_ratio = 100/9 ≈ 11.11
    // L/D = clamp(8 + 11.11 * 0.7, 8, 22) = clamp(15.78, 8, 22) = 15.78
    assert.ok(m.estimated_lift_to_drag != null);
    assert.ok(m.estimated_lift_to_drag! > 8);
  });

  it("returns undefined for missing values", () => {
    const m = extractCompareMetrics(makeItem());
    assert.equal(m.wingspan_m, undefined);
    assert.equal(m.fuselage_length_m, undefined);
    assert.equal(m.wing_area_m2, undefined);
  });
});
