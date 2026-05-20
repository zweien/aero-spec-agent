"use client";

import { type JSX } from "react";

export type CompareMetricCellProps = {
  value?: number | string | null;
  unit?: string;
  isBest?: boolean;
  isRisk?: boolean;
};

export function CompareMetricCell({ value, unit, isBest, isRisk }: CompareMetricCellProps): JSX.Element {
  if (value == null) {
    return <span style={{ color: "var(--text-muted)", fontStyle: "italic", fontSize: 12 }}>暂无</span>;
  }

  const display = typeof value === "number"
    ? (Number.isInteger(value) ? String(value) : value.toFixed(2))
    : String(value);

  const bg = isBest
    ? "rgba(34,197,94,0.08)"
    : isRisk
      ? "rgba(234,179,8,0.08)"
      : "transparent";

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 2,
        padding: "2px 6px",
        borderRadius: 4,
        background: bg,
        fontSize: 12,
        fontWeight: isBest ? 600 : 400,
        color: isBest ? "var(--success, #16a34a)" : isRisk ? "var(--warning, #ca8a04)" : "var(--text)",
      }}
    >
      {display}
      {isBest && <span style={{ fontSize: 10 }}>&#9733;</span>}
      {unit && <span style={{ fontSize: 10, color: "var(--text-muted)", fontWeight: 400 }}>{unit}</span>}
    </span>
  );
}
