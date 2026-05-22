"use client";

import { type JSX } from "react";
import type { CompareMetricSource, MetricConfidence } from "./types";
import { SOURCE_LABELS } from "./metricExtractors";

export type CompareMetricCellProps = {
  value?: number | string | null;
  unit?: string;
  isBest?: boolean;
  isRisk?: boolean;
  source?: CompareMetricSource;
  confidence?: MetricConfidence;
};

export function CompareMetricCell({ value, unit, isBest, isRisk, source, confidence }: CompareMetricCellProps): JSX.Element {
  if (value == null || source === "missing") {
    return (
      <span
        style={{ color: "var(--text-muted)", fontStyle: "italic", fontSize: 12 }}
        title={source ? SOURCE_LABELS[source] : undefined}
      >
        暂无
      </span>
    );
  }

  const display = typeof value === "number"
    ? (Number.isInteger(value) ? String(value) : value.toFixed(2))
    : String(value);

  const bg = isBest
    ? "var(--success-bg)"
    : isRisk || confidence === "low"
      ? "var(--warning-bg)"
      : "transparent";

  const color = isBest
    ? "var(--success)"
    : isRisk || confidence === "low"
      ? "var(--warning)"
      : "var(--text)";

  const sourceTitle = source ? SOURCE_LABELS[source] : undefined;

  return (
    <span
      title={sourceTitle}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 2,
        padding: "2px 6px",
        borderRadius: 4,
        background: bg,
        fontSize: 12,
        fontWeight: isBest ? 600 : 400,
        color,
      }}
    >
      {display}
      {isBest && <span style={{ fontSize: 10 }}>&#9733;</span>}
      {unit && <span style={{ fontSize: 10, color: "var(--text-muted)", fontWeight: 400 }}>{unit}</span>}
    </span>
  );
}
