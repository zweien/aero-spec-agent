import assert from "node:assert/strict";
import test from "node:test";

import {
  buildAeroSection,
  buildDesignReportMarkdown,
  buildSpecTable,
} from "./reportExport.ts";
import type { VspaeroAnalysisEntry } from "@/app/page";

const specEcho = {
  aircraft: { name: { value: "Delta_Recon_9" }, layout: { value: "conventional" } },
  wing: {
    span: { value: 9, unit: "m" },
    planform: { value: "delta" },
  },
  mission: {
    cruise_speed: { value: 320, unit: "km/h" },
  },
};

test("buildSpecTable renders localized scalar rows and skips empties", () => {
  const md = buildSpecTable(specEcho);
  assert.match(md, /\| 总体 \| 设计名称 \| Delta_Recon_9 \|/);
  assert.match(md, /\| 机翼 \| 翼展 \| 9 m \|/);
  assert.match(md, /\| 机翼 \| 翼平面形状 \| delta \|/);
  assert.match(md, /\| 任务 \| 巡航速度 \| 320 km\/h \|/);
});

test("buildAeroSection labels the solver and includes sweep table", () => {
  const analysis: VspaeroAnalysisEntry = {
    status: "success",
    method: "VSPAERO_panel",
    optimal_ld: 11.2,
    optimal_cl: 0.394,
    optimal_alpha: 7,
    alpha_sweep: [
      { alpha: 0, cl: 0.06, cd: 0.022, cm: 0 },
      { alpha: 7, cl: 0.4, cd: 0.03, cm: -0.5 },
    ],
  };
  const md = buildAeroSection(analysis);
  assert.match(md, /VSPAERO 面元法/);
  assert.match(md, /L\/D：11\.20/);
  assert.match(md, /\| α \(°\) \| CL \| CD \| CM \| L\/D \|/);
});

test("buildAeroSection flags simulated and skipped analyses", () => {
  const fake: VspaeroAnalysisEntry = {
    status: "success",
    method: "fake_vspaero",
    optimal_ld: 8,
    optimal_cl: 0.3,
    optimal_alpha: 4,
    alpha_sweep: [],
  };
  assert.match(buildAeroSection(fake), /模拟数据（非真实求解）/);

  const skipped: VspaeroAnalysisEntry = {
    status: "skipped",
    method: "VSPAERO_panel",
    optimal_ld: 0,
    optimal_cl: 0,
    optimal_alpha: 0,
    alpha_sweep: [],
  };
  const md = buildAeroSection(skipped);
  assert.match(md, /状态：skipped/);
  assert.doesNotMatch(md, /L\/D：/);
});

test("buildDesignReportMarkdown composes all sections with disclaimer", () => {
  const md = buildDesignReportMarkdown({
    designId: "d-1",
    versionNo: 3,
    specEcho,
    designRules: [
      {
        rule_id: "r1",
        label: "展弦比范围",
        status: "warn",
        value: 2.2,
        expected: "3.0 ~ 12.0",
        message: "偏低",
      },
    ],
    perfEstimates: [
      {
        estimate_id: "p1",
        label: "最大起飞重量",
        value: 1000,
        unit: "kg",
        confidence: "medium",
        method: "statistical",
        status: "reasonable",
        typical_range: "800 ~ 1200 kg",
        message: "合理",
      },
    ],
    aeroAnalysis: null,
    designMetrics: { wingspan_m: 9, aspect_ratio: 4.09 },
  });

  assert.match(md, /# 设计报告 — Delta_Recon_9（v3）/);
  assert.match(md, /## 设计参数/);
  assert.match(md, /## 设计检查/);
  assert.match(md, /\| 展弦比范围 \| 警告 \|/);
  assert.match(md, /## 性能估算/);
  assert.match(md, /## 设计指标/);
  assert.match(md, /- 翼展 \(m\)：9/);
  assert.match(md, /不能替代详细仿真或风洞试验/);
});
