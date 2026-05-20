import type { CompareMetrics } from "./types";

type MetricKey = keyof CompareMetrics;

const HIGHER_IS_BETTER: Set<string> = new Set([
  "estimated_lift_to_drag",
  "estimated_range_km",
  "estimated_endurance_h",
  "aspect_ratio",
]);

const LOWER_IS_BETTER: Set<string> = new Set([
  "defaulted_fields_count",
  "missing_metrics_count",
]);

const RISK_ORDER: Record<string, number> = { low: 0, medium: 1, high: 2, unknown: 3 };

/**
 * For a given metric key and array of items, return the indices of the "best" items.
 * Returns empty array if fewer than 2 items, or if all values are undefined.
 */
export function findBestIndices(key: MetricKey, metrics: CompareMetrics[]): number[] {
  if (metrics.length < 2) return [];

  const numValues: { idx: number; val: number }[] = [];
  for (let i = 0; i < metrics.length; i++) {
    const raw = metrics[i][key];
    if (raw == null) continue;
    numValues.push({ idx: i, val: typeof raw === "number" ? raw : -1 });
  }
  if (numValues.length < 2) return [];

  if (HIGHER_IS_BETTER.has(key)) {
    const max = Math.max(...numValues.map((v) => v.val));
    return numValues.filter((v) => v.val === max).map((v) => v.idx);
  }

  if (LOWER_IS_BETTER.has(key)) {
    const min = Math.min(...numValues.map((v) => v.val));
    return numValues.filter((v) => v.val === min).map((v) => v.idx);
  }

  return [];
}

export function findBestRisk(metrics: CompareMetrics[]): number[] {
  if (metrics.length < 2) return [];
  const scored = metrics
    .map((m, i) => ({ idx: i, score: RISK_ORDER[m.risk_level ?? "unknown"] ?? 3 }));
  const min = Math.min(...scored.map((s) => s.score));
  return scored.filter((s) => s.score === min).map((s) => s.idx);
}

export function isBest(key: MetricKey, idx: number, metrics: CompareMetrics[]): boolean {
  if (key === "risk_level") return findBestRisk(metrics).includes(idx);
  return findBestIndices(key, metrics).includes(idx);
}
