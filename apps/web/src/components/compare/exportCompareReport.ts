import type { CompareItem } from "./types";
import { extractCompareMetrics } from "./metricExtractors";
import { SOURCE_LABELS } from "./metricExtractors";
import type { CompareMetricSource, CompareMetrics } from "./types";

type MetricRow = {
  key: keyof CompareMetrics;
  label: string;
  unit?: string;
};

const METRIC_ROWS: MetricRow[] = [
  { key: "wingspan_m", label: "翼展", unit: "m" },
  { key: "fuselage_length_m", label: "机身长度", unit: "m" },
  { key: "wing_area_m2", label: "翼面积", unit: "m²" },
  { key: "aspect_ratio", label: "展弦比" },
  { key: "estimated_lift_to_drag", label: "估算升阻比" },
  { key: "estimated_range_km", label: "估算航程", unit: "km" },
  { key: "estimated_endurance_h", label: "估算续航", unit: "h" },
  { key: "wing_loading_kg_m2", label: "翼载荷", unit: "kg/m²" },
  { key: "risk_level", label: "风险等级" },
];

function formatVal(value: unknown): string {
  if (value == null) return "-";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  return String(value);
}

function getNow(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}`;
}

export function getExportFilename(): string {
  return `compare-report-${getNow()}.md`;
}

export function exportCompareReport(items: CompareItem[]): string {
  if (!items || items.length < 2) {
    return "";
  }

  const metricsMap = items.map((item) =>
    item.metrics ?? extractCompareMetrics(item),
  );

  const lines: string[] = [];

  // Title
  lines.push("# 方案对比报告");
  lines.push("");

  // Schemes section
  lines.push("## 对比方案");
  lines.push("");
  for (const item of items) {
    const name = item.name ?? `v${item.versionNo}`;
    lines.push(`- **${name}** (版本 ${item.versionNo})`);
  }
  lines.push("");

  // Metrics table
  lines.push("## 指标对比表");
  lines.push("");

  // Table header
  const headers = ["指标", ...items.map((item) => item.name ?? `v${item.versionNo}`)];
  lines.push(`| ${headers.join(" | ")} |`);
  lines.push(`| ${headers.map(() => "---").join(" | ")} |`);

  // Table rows
  for (const row of METRIC_ROWS) {
    const cells = [row.label];
    for (let i = 0; i < items.length; i++) {
      const m = metricsMap[i];
      const raw = m?.[row.key];
      let val = formatVal(raw);
      if (row.unit && raw != null) {
        val += ` ${row.unit}`;
      }
      cells.push(val);
    }
    lines.push(`| ${cells.join(" | ")} |`);
  }
  lines.push("");

  // Best values
  lines.push("## 最优项说明");
  lines.push("");
  lines.push("指标表中 ★ 标记的数值为该指标在所有方案中的最优值。");
  lines.push("- 翼展、翼面积、展弦比、升阻比、航程、续航：越大越优");
  lines.push("- 翼载荷：越小越优");
  lines.push("- 风险等级：low > medium > high");
  lines.push("");

  // Confidence section
  lines.push("## 可信度说明");
  lines.push("");
  lines.push("**当前指标为概念设计阶段估算，用于方案初筛，不代表高保真气动或结构分析结果。**");
  lines.push("");

  // Source breakdown per item
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    const m = metricsMap[i];
    const name = item.name ?? `v${item.versionNo}`;
    const sources = m.metric_sources as Record<string, CompareMetricSource> | undefined;
    if (sources) {
      const sourceCounts: Record<string, number> = {};
      for (const src of Object.values(sources)) {
        const label = SOURCE_LABELS[src];
        sourceCounts[label] = (sourceCounts[label] || 0) + 1;
      }
      const summary = Object.entries(sourceCounts)
        .map(([label, count]) => `${label} ${count} 项`)
        .join("，");
      lines.push(`- **${name}**: ${summary}`);
    }
  }
  lines.push("");

  // Warnings
  const allWarnings = metricsMap.flatMap((m) => m.warnings ?? []);
  if (allWarnings.length > 0) {
    lines.push("### 注意事项");
    lines.push("");
    const unique = [...new Set(allWarnings)];
    for (const w of unique) {
      lines.push(`- ${w}`);
    }
    lines.push("");
  }

  return lines.join("\n");
}
