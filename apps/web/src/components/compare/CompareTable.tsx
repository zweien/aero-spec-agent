"use client";

import { type JSX } from "react";
import type { CompareItem, CompareMetrics } from "./types";
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
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr>
            <th
              style={{
                textAlign: "left",
                padding: "6px 8px",
                borderBottom: "2px solid var(--border-default)",
                fontWeight: 600,
                color: "var(--text-muted)",
                fontSize: 11,
                minWidth: 100,
                position: "sticky",
                left: 0,
                background: "var(--bg-elevated)",
              }}
            >
              指标
            </th>
            {items.map((item) => (
              <th
                key={item.id}
                style={{
                  textAlign: "center",
                  padding: "6px 8px",
                  borderBottom: "2px solid var(--border-default)",
                  fontWeight: 600,
                  color: "var(--text)",
                  fontSize: 11,
                  minWidth: 90,
                }}
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
          style={{
            padding: "8px 8px 3px",
            fontSize: 10,
            fontWeight: 700,
            color: "var(--text-muted)",
            textTransform: "uppercase",
            letterSpacing: 0.5,
            borderBottom: "1px solid var(--border-default)",
          }}
        >
          {group.label}
        </td>
      </tr>
      {group.rows.map((row) => (
        <tr key={row.key}>
          <td
            style={{
              padding: "4px 8px",
              borderBottom: "1px solid var(--border-default)",
              color: "var(--text)",
              fontWeight: 500,
              position: "sticky",
              left: 0,
              background: "var(--bg-elevated)",
            }}
          >
            {row.label}
          </td>
          {items.map((_, i) => {
            const m = metricsMap[i];
            const raw = m?.[row.key];
            const best = isBest(row.key, i, metricsMap);
            const isRisk = row.key === "risk_level" && raw === "medium" || raw === "high";

            return (
              <td
                key={i}
                style={{
                  textAlign: "center",
                  padding: "4px 8px",
                  borderBottom: "1px solid var(--border-default)",
                }}
              >
                <CompareMetricCell
                  value={raw}
                  unit={row.unit}
                  isBest={best}
                  isRisk={!!isRisk}
                />
              </td>
            );
          })}
        </tr>
      ))}
    </>
  );
}
