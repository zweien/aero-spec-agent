import type {
  DesignRuleEntry,
  PerformanceEstimateEntry,
  VspaeroAnalysisEntry,
} from "@/app/page";

export type DesignReportSpecEcho = Record<string, unknown>;

export type DesignReportInput = {
  designId: string;
  versionNo: number;
  specEcho?: DesignReportSpecEcho | null;
  designRules?: DesignRuleEntry[] | null;
  perfEstimates?: PerformanceEstimateEntry[] | null;
  aeroAnalysis?: VspaeroAnalysisEntry | null;
  designMetrics?: Record<string, unknown> | null;
  generatedAt?: Date;
};

type ScalarLike = { value: unknown; unit?: string | null };

function isScalarLike(val: unknown): val is ScalarLike {
  return (
    typeof val === "object" &&
    val !== null &&
    "value" in val &&
    !Array.isArray(val)
  );
}

function scalarText(val: unknown): string | null {
  if (val == null) return null;
  if (isScalarLike(val)) {
    const v = val.value;
    if (v == null || v === "") return null;
    return val.unit ? `${v} ${val.unit}` : `${v}`;
  }
  if (typeof val === "object") return null;
  return String(val);
}

const SPEC_SECTION_LABELS: Record<string, string> = {
  aircraft: "总体",
  mission: "任务",
  fuselage: "机身",
  wing: "机翼",
  horizontal_tail: "平尾",
  vertical_tail: "垂尾",
  tail: "尾翼",
  engine: "动力",
};

const SPEC_FIELD_LABELS: Record<string, string> = {
  name: "设计名称",
  type: "类型",
  layout: "布局",
  cruise_speed: "巡航速度",
  cruise_altitude: "巡航高度",
  range: "航程",
  endurance: "续航",
  payload: "载荷",
  priority: "设计优先级",
  length: "长度",
  max_diameter: "最大直径",
  position: "位置",
  z_rel_location: "展向位置",
  span: "翼展",
  root_chord: "根弦长",
  tip_chord: "尖弦长",
  sweep: "后掠角",
  dihedral: "上反角",
  incidence: "安装角",
  airfoil: "翼型",
  planform: "翼平面形状",
  sections: "截面段数",
  count: "数量",
  type_tail: "尾翼类型",
};

function specFieldLabel(key: string): string {
  return SPEC_FIELD_LABELS[key] ?? key;
}

export function buildSpecTable(specEcho: DesignReportSpecEcho): string {
  const rows: string[] = ["| 类别 | 参数 | 值 |", "|------|------|----|"];
  for (const [sectionKey, section] of Object.entries(specEcho)) {
    if (typeof section !== "object" || section == null || Array.isArray(section)) {
      continue;
    }
    const sectionLabel = SPEC_SECTION_LABELS[sectionKey] ?? sectionKey;
    for (const [fieldKey, fieldValue] of Object.entries(section)) {
      const text = scalarText(fieldValue);
      if (text == null) continue;
      rows.push(`| ${sectionLabel} | ${specFieldLabel(fieldKey)} | ${text} |`);
    }
  }
  return rows.length > 3 ? rows.join("\n") : "_无参数数据_";
}

const RULE_STATUS_LABEL: Record<string, string> = {
  pass: "通过",
  warn: "警告",
  fail: "失败",
  skip: "跳过",
};

export function buildDesignRulesTable(rules: DesignRuleEntry[]): string {
  const rows: string[] = [
    "| 规则 | 状态 | 当前值 | 期望 | 说明 |",
    "|------|------|--------|------|------|",
  ];
  for (const r of rules) {
    rows.push(
      `| ${r.label} | ${RULE_STATUS_LABEL[r.status] ?? r.status} | ${r.value} | ${r.expected} | ${r.message ?? ""} |`,
    );
  }
  return rows.join("\n");
}

export function buildPerfTable(estimates: PerformanceEstimateEntry[]): string {
  const rows: string[] = [
    "| 指标 | 估算值 | 典型范围 | 置信度 | 说明 |",
    "|------|--------|----------|--------|------|",
  ];
  for (const e of estimates) {
    const value = typeof e.value === "number" ? e.value : String(e.value);
    rows.push(
      `| ${e.label} | ${value}${e.unit ? ` ${e.unit}` : ""} | ${e.typical_range} | ${e.confidence} | ${e.message ?? ""} |`,
    );
  }
  return rows.join("\n");
}

export function buildAeroSection(aero: VspaeroAnalysisEntry): string {
  const lines: string[] = [];
  const methodLabel =
    aero.method === "VSPAERO_panel"
      ? "VSPAERO 面元法"
      : aero.method === "fake_vspaero"
        ? "模拟数据（非真实求解）"
        : aero.method;
  lines.push(`- 求解器：${methodLabel}（状态：${aero.status}）`);
  if (aero.status === "success") {
    lines.push(`- 最优升阻比 L/D：${aero.optimal_ld.toFixed(2)}（CL=${aero.optimal_cl.toFixed(3)}, α=${aero.optimal_alpha.toFixed(1)}°）`);
    if (aero.cd0_estimate != null) lines.push(`- 零升阻力 CD₀：${aero.cd0_estimate.toFixed(4)}`);
    if (aero.cl_alpha != null) lines.push(`- 升力线斜率 CLα：${aero.cl_alpha.toFixed(3)} /rad`);
    if (aero.alpha_sweep.length > 0) {
      lines.push("", "| α (°) | CL | CD | CM | L/D |", "|-------|----|----|----|-----|");
      for (const pt of aero.alpha_sweep) {
        const ld = pt.cd > 1e-6 ? (pt.cl / pt.cd).toFixed(1) : "—";
        lines.push(
          `| ${pt.alpha.toFixed(1)} | ${pt.cl.toFixed(4)} | ${pt.cd.toFixed(5)} | ${pt.cm.toFixed(4)} | ${ld} |`,
        );
      }
    }
  } else if (aero.error_message) {
    lines.push(`- 错误：${aero.error_message}`);
  }
  return lines.join("\n");
}

export function buildMetricsSection(metrics: Record<string, unknown>): string {
  const entries: Array<[string, string]> = [];
  const metricDefs: Array<[string, string]> = [
    ["wingspan_m", "翼展 (m)"],
    ["fuselage_length_m", "机身长度 (m)"],
    ["wing_area_m2", "翼面积 (m²)"],
    ["aspect_ratio", "展弦比"],
    ["estimated_lift_to_drag", "升阻比"],
    ["estimated_range_km", "航程 (km)"],
    ["estimated_endurance_h", "续航 (h)"],
    ["wing_loading_kg_m2", "翼载荷 (kg/m²)"],
  ];
  for (const [key, label] of metricDefs) {
    const v = metrics[key];
    if (typeof v === "number") {
      entries.push([label, String(Math.round(v * 100) / 100)]);
    }
  }
  if (entries.length === 0) return "_无设计指标_";
  return entries.map(([label, v]) => `- ${label}：${v}`).join("\n");
}

export function buildDesignReportMarkdown(input: DesignReportInput): string {
  const {
    designId,
    versionNo,
    specEcho,
    designRules,
    perfEstimates,
    aeroAnalysis,
    designMetrics,
    generatedAt = new Date(),
  } = input;

  const name = scalarText(
    specEcho && typeof specEcho.aircraft === "object"
      ? (specEcho.aircraft as Record<string, unknown>).name
      : null,
  ) ?? "未命名设计";

  const parts: string[] = [];
  parts.push(`# 设计报告 — ${name}（v${versionNo}）`);
  parts.push(`\n> 设计 ID：\`${designId}\`　生成时间：${generatedAt.toLocaleString("zh-CN")}`);

  parts.push("\n## 设计参数");
  parts.push(specEcho ? buildSpecTable(specEcho) : "_无参数数据_");

  if (designRules && designRules.length > 0) {
    parts.push("\n## 设计检查");
    parts.push(buildDesignRulesTable(designRules));
  }

  if (perfEstimates && perfEstimates.length > 0) {
    parts.push("\n## 性能估算");
    parts.push(buildPerfTable(perfEstimates));
  }

  if (aeroAnalysis) {
    parts.push("\n## 气动分析");
    parts.push(buildAeroSection(aeroAnalysis));
  }

  if (designMetrics) {
    parts.push("\n## 设计指标");
    parts.push(buildMetricsSection(designMetrics));
  }

  parts.push("\n---");
  parts.push(
    "_本报告由 AeroSpec Agent 自动生成；性能与气动数值为概念设计阶段的估算，仅用于方案筛选，不能替代详细仿真或风洞试验。_",
  );
  return parts.join("\n");
}

export function downloadTextFile(filename: string, content: string, mime = "text/markdown"): void {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
