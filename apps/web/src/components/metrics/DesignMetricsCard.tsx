"use client";

import { type JSX } from "react";
import type { CompareMetrics, MetricConfidence } from "../compare/types";

export type DesignMetricsCardProps = {
  metrics: CompareMetrics;
  versionLabel?: string;
};

type MetricDisplay = {
  key: string;
  label: string;
  value: string;
  unit?: string;
};

const CONFIDENCE_LABELS: Record<MetricConfidence, string> = {
  high: "高",
  medium: "中",
  low: "低",
};

export function DesignMetricsCard({ metrics, versionLabel }: DesignMetricsCardProps): JSX.Element {
  const displays: MetricDisplay[] = [];

  if (metrics.wingspan_m != null)
    displays.push({ key: "wingspan_m", label: "翼展", value: fmt(metrics.wingspan_m), unit: "m" });
  if (metrics.fuselage_length_m != null)
    displays.push({ key: "fuselage_length_m", label: "机身长度", value: fmt(metrics.fuselage_length_m), unit: "m" });
  if (metrics.wing_area_m2 != null)
    displays.push({ key: "wing_area_m2", label: "翼面积", value: fmt(metrics.wing_area_m2), unit: "m²" });
  if (metrics.aspect_ratio != null)
    displays.push({ key: "aspect_ratio", label: "展弦比", value: fmt(metrics.aspect_ratio) });
  if (metrics.estimated_lift_to_drag != null)
    displays.push({ key: "estimated_lift_to_drag", label: "升阻比", value: fmt(metrics.estimated_lift_to_drag) });
  if (metrics.estimated_range_km != null)
    displays.push({ key: "estimated_range_km", label: "航程", value: fmt(metrics.estimated_range_km), unit: "km" });
  if (metrics.estimated_endurance_h != null)
    displays.push({ key: "estimated_endurance_h", label: "续航", value: fmt(metrics.estimated_endurance_h), unit: "h" });
  if (metrics.wing_loading_kg_m2 != null)
    displays.push({ key: "wing_loading_kg_m2", label: "翼载荷", value: fmt(metrics.wing_loading_kg_m2), unit: "kg/m²" });

  const confidence = metrics.confidence ?? "medium";
  const riskLevel = metrics.risk_level ?? "unknown";
  const warnings = metrics.warnings ?? [];

  return (
    <div
      style={{
        border: "1px solid var(--border-default)",
        borderRadius: 8,
        padding: 12,
        background: "var(--bg-surface)",
        fontSize: 12,
      }}
    >
      {versionLabel && (
        <div style={{ fontWeight: 600, marginBottom: 8, color: "var(--text)" }}>
          {versionLabel} 设计指标
        </div>
      )}

      {/* Metrics grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
          gap: "6px 16px",
        }}
      >
        {displays.map((d) => (
          <div key={d.key} style={{ display: "flex", justifyContent: "space-between", gap: 4 }}>
            <span style={{ color: "var(--text-muted)" }}>{d.label}</span>
            <span style={{ fontWeight: 500, color: "var(--text)" }}>
              {d.value}{d.unit ? ` ${d.unit}` : ""}
            </span>
          </div>
        ))}
      </div>

      {/* Risk + Confidence */}
      <div
        style={{
          display: "flex",
          gap: 12,
          marginTop: 8,
          paddingTop: 8,
          borderTop: "1px solid var(--border-default)",
          fontSize: 11,
          color: "var(--text-muted)",
        }}
      >
        <span>
          风险等级: <span style={{ color: riskColor(riskLevel), fontWeight: 500 }}>{riskLabel(riskLevel)}</span>
        </span>
        <span>
          置信度: <span style={{ fontWeight: 500 }}>{CONFIDENCE_LABELS[confidence]}</span>
        </span>
      </div>

      {/* Warnings */}
      {warnings.length > 0 && (
        <div style={{ marginTop: 6, fontSize: 11, color: "var(--warning, #ca8a04)" }}>
          {warnings.map((w, i) => (
            <div key={i}>{w}</div>
          ))}
        </div>
      )}

      {/* Disclaimer */}
      <div
        style={{
          marginTop: 8,
          paddingTop: 8,
          borderTop: "1px solid var(--border-default)",
          fontSize: 10,
          color: "var(--text-muted)",
          fontStyle: "italic",
        }}
      >
        概念设计估算，仅用于初步方案筛选。
      </div>
    </div>
  );
}

function fmt(v: number): string {
  return Number.isInteger(v) ? String(v) : v.toFixed(2);
}

function riskColor(level: string): string {
  switch (level) {
    case "low": return "var(--success, #16a34a)";
    case "medium": return "var(--warning, #ca8a04)";
    case "high": return "var(--error, #dc2626)";
    default: return "var(--text-muted)";
  }
}

function riskLabel(level: string): string {
  switch (level) {
    case "low": return "低";
    case "medium": return "中";
    case "high": return "高";
    default: return "未知";
  }
}
