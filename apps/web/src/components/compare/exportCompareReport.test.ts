import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { exportCompareReport, getExportFilename } from "./exportCompareReport.ts";
import type { CompareItem } from "./types.ts";

function makeItem(overrides: Partial<CompareItem> = {}): CompareItem {
  return {
    id: `test-${Math.random().toString(36).slice(2, 8)}`,
    designId: "d1",
    versionNo: 1,
    source: "version",
    ...overrides,
  };
}

describe("exportCompareReport", () => {
  it("returns empty string for fewer than 2 items", () => {
    assert.equal(exportCompareReport([]), "");
    assert.equal(exportCompareReport([makeItem()]), "");
  });

  it("generates report for 2+ items", () => {
    const items = [
      makeItem({
        id: "v1",
        versionNo: 1,
        spec: { wing: { span: { value: 12 } } },
        validationReport: {
          design_metrics: {
            wingspan_m: 12,
            wing_area_m2: 16,
            aspect_ratio: 9,
            estimated_lift_to_drag: 14,
            estimated_range_km: 3500,
            estimated_endurance_h: 20,
            risk_level: "low",
          },
        },
      }),
      makeItem({
        id: "v2",
        versionNo: 2,
        spec: { wing: { span: { value: 15 } } },
        validationReport: {
          design_metrics: {
            wingspan_m: 15,
            wing_area_m2: 22,
            aspect_ratio: 10.2,
            estimated_lift_to_drag: 16,
            estimated_range_km: 4000,
            estimated_endurance_h: 22,
            risk_level: "low",
          },
        },
      }),
    ];
    const report = exportCompareReport(items);
    assert.ok(report.length > 0);
    assert.ok(report.includes("# 方案对比报告"));
    assert.ok(report.includes("## 对比方案"));
    assert.ok(report.includes("## 指标对比表"));
    assert.ok(report.includes("## 最优项说明"));
    assert.ok(report.includes("## 可信度说明"));
    assert.ok(report.includes("概念设计阶段估算"));
  });

  it("includes metric values in the table", () => {
    const items = [
      makeItem({ versionNo: 1, validationReport: { design_metrics: { wingspan_m: 12 } } }),
      makeItem({ versionNo: 2, validationReport: { design_metrics: { wingspan_m: 15 } } }),
    ];
    const report = exportCompareReport(items);
    assert.ok(report.includes("12"));
    assert.ok(report.includes("15"));
  });

  it("does not contain NaN or undefined", () => {
    const items = [
      makeItem({ versionNo: 1 }),
      makeItem({ versionNo: 2 }),
    ];
    const report = exportCompareReport(items);
    assert.ok(!report.includes("NaN"));
    assert.ok(!report.includes("undefined"));
    assert.ok(!report.includes("[object Object]"));
  });

  it("uses - for missing values", () => {
    const items = [
      makeItem({ versionNo: 1 }),
      makeItem({ versionNo: 2 }),
    ];
    const report = exportCompareReport(items);
    // Missing values should show as "-"
    const lines = report.split("\n");
    const wingLine = lines.find((l) => l.includes("翼展"));
    assert.ok(wingLine);
    assert.ok(wingLine!.includes("-"));
  });

  it("getExportFilename returns expected format", () => {
    const name = getExportFilename();
    assert.ok(name.startsWith("compare-report-"));
    assert.ok(name.endsWith(".md"));
    assert.ok(name.length > "compare-report-.md".length);
  });

  it("includes source breakdown in confidence section", () => {
    const items = [
      makeItem({
        versionNo: 1,
        validationReport: {
          design_metrics: { wingspan_m: 12, wing_area_m2: 16 },
        },
      }),
      makeItem({
        versionNo: 2,
        validationReport: {
          design_metrics: { wingspan_m: 15, wing_area_m2: 22 },
        },
      }),
    ];
    const report = exportCompareReport(items);
    assert.ok(report.includes("后端估算"));
  });

  it("handles items with warnings", () => {
    const items = [
      makeItem({
        versionNo: 1,
        validationReport: {
          design_metrics: { wingspan_m: 12 },
        },
      }),
      makeItem({
        versionNo: 2,
        validationReport: {
          design_metrics: { wingspan_m: 15 },
        },
      }),
    ];
    const report = exportCompareReport(items);
    // Should complete without error
    assert.ok(report.includes("注意事项") || report.includes("概念设计"));
  });
});
