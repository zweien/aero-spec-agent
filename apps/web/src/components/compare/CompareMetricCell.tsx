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
        className="compare-metric-cell compare-metric-missing"
        title={source ? SOURCE_LABELS[source] : undefined}
      >
        暂无
      </span>
    );
  }

  const display = typeof value === "number"
    ? (Number.isInteger(value) ? String(value) : value.toFixed(2))
    : String(value);

  const sourceTitle = source ? SOURCE_LABELS[source] : undefined;
  const className = [
    "compare-metric-cell",
    isBest ? "compare-metric-best" : "",
    !isBest && (isRisk || confidence === "low") ? "compare-metric-warning" : "",
  ].filter(Boolean).join(" ");

  return (
    <span
      title={sourceTitle}
      className={className}
    >
      {display}
      {isBest && <span className="compare-metric-star">&#9733;</span>}
      {unit && <span className="compare-metric-unit">{unit}</span>}
    </span>
  );
}
