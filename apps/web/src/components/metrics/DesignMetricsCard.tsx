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
    <div className="design-metrics-card">
      {versionLabel && (
        <div className="design-metrics-title">
          {versionLabel} 设计指标
        </div>
      )}

      {/* Metrics grid */}
      <div className="design-metrics-grid">
        {displays.map((d) => (
          <div key={d.key} className="design-metrics-row">
            <span className="design-metrics-label">{d.label}</span>
            <span className="design-metrics-value">
              {d.value}{d.unit ? ` ${d.unit}` : ""}
            </span>
          </div>
        ))}
      </div>

      {/* Risk + Confidence */}
      <div className="design-metrics-meta">
        <span>
          风险等级: <span className={`risk-level risk-level-${riskLevel}`}>{riskLabel(riskLevel)}</span>
        </span>
        <span>
          置信度: <span className="design-metrics-confidence">{CONFIDENCE_LABELS[confidence]}</span>
        </span>
      </div>

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="design-metrics-warnings">
          {warnings.map((w, i) => (
            <div key={i}>{w}</div>
          ))}
        </div>
      )}

      {/* Disclaimer */}
      <div className="design-metrics-disclaimer">
        概念设计估算，仅用于初步方案筛选。
      </div>
    </div>
  );
}

function fmt(v: number): string {
  return Number.isInteger(v) ? String(v) : v.toFixed(2);
}

function riskLabel(level: string): string {
  switch (level) {
    case "low": return "低";
    case "medium": return "中";
    case "high": return "高";
    default: return "未知";
  }
}
