"use client";

import { type JSX } from "react";
import type { CompareItem, CompareMetrics, CompareMetricSource, MetricConfidence } from "./types";
import { extractCompareMetrics } from "./metricExtractors";
import { isBest } from "./bestValue";
import { CompareMetricCell } from "./CompareMetricCell";

export type CompareTableProps = {
  items: CompareItem[];
};

type MetricRow = {
  key: keyof CompareMetrics;
  label: string;
  unit?: string;
  group: string;
  format?: (v: number) => string;
};

const METRIC_ROWS: MetricRow[] = [
  // 基础尺寸
  { key: "wingspan_m", label: "翼展", unit: "m", group: "基础尺寸" },
  { key: "fuselage_length_m", label: "机身长度", unit: "m", group: "基础尺寸" },
  { key: "wing_area_m2", label: "翼面积", unit: "m²", group: "基础尺寸" },
  { key: "aspect_ratio", label: "展弦比", group: "基础尺寸" },
  // 性能估算
  { key: "estimated_lift_to_drag", label: "估算升阻比", group: "性能估算" },
  { key: "estimated_range_km", label: "估算航程", unit: "km", group: "性能估算" },
  { key: "estimated_endurance_h", label: "估算续航", unit: "h", group: "性能估算" },
  { key: "wing_loading_kg_m2", label: "翼载荷", unit: "kg/m²", group: "性能估算" },
  // 可信度与风险
  { key: "risk_level", label: "风险等级", group: "可信度与风险" },
  { key: "defaulted_fields_count", label: "默认补全参数", unit: "项", group: "可信度与风险" },
  { key: "missing_metrics_count", label: "缺失指标", unit: "项", group: "可信度与风险" },
];

const GROUP_ORDER = ["基础尺寸", "性能估算", "可信度与风险"];

export function CompareTable({ items }: CompareTableProps): JSX.Element {
  const metricsMap = items.map((item) => {
    if (item.metrics) return item.metrics;
    return extractCompareMetrics(item);
  });

  const groups = GROUP_ORDER.map((g) => ({
    label: g,
    rows: METRIC_ROWS.filter((r) => r.group === g),
  }));

  return (
    <div className="compare-table-scroll">
      <table className="compare-table compare-drawer-table">
        <thead>
          <tr>
            <th className="compare-metric-heading">
              指标
            </th>
            {items.map((item) => (
              <th
                key={item.id}
                className="compare-item-heading"
              >
                {item.name ?? `v${item.versionNo}`}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {groups.map((group) => (
            <MetricGroup
              key={group.label}
              group={group}
              items={items}
              metricsMap={metricsMap}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MetricGroup({
  group,
  items,
  metricsMap,
}: {
  group: { label: string; rows: MetricRow[] };
  items: CompareItem[];
  metricsMap: CompareMetrics[];
}): JSX.Element {
  return (
    <>
      <tr>
        <td
          colSpan={items.length + 1}
          className="compare-metric-group"
        >
          {group.label}
        </td>
      </tr>
      {group.rows.map((row) => (
        <tr key={row.key}>
          <td className="compare-metric-label">
            {row.label}
          </td>
          {items.map((_, i) => {
            const m = metricsMap[i];
            const raw = m?.[row.key];
            const cellValue = typeof raw === "number" || typeof raw === "string" ? raw : undefined;
            const best = isBest(row.key, i, metricsMap);
            const isRisk = row.key === "risk_level" && raw === "medium" || raw === "high";
            const metricSources = m?.metric_sources as Record<string, CompareMetricSource> | undefined;
            const source = metricSources?.[row.key] as CompareMetricSource | undefined;
            const confidence = m?.confidence as MetricConfidence | undefined;

            return (
              <td
                key={i}
                className="compare-metric-value"
              >
                <CompareMetricCell
                  value={cellValue}
                  unit={row.unit}
                  isBest={best}
                  isRisk={!!isRisk}
                  source={source}
                  confidence={confidence}
                />
              </td>
            );
          })}
        </tr>
      ))}
    </>
  );
}
