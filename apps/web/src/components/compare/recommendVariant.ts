import type { CompareItem, CompareMetrics } from "./types";
import { extractCompareMetrics } from "./metricExtractors";

type MetricWeight = {
  key: keyof CompareMetrics;
  direction: "higher" | "lower";
  weight: number;
};

const WEIGHTS: MetricWeight[] = [
  { key: "estimated_range_km", direction: "higher", weight: 3 },
  { key: "estimated_lift_to_drag", direction: "higher", weight: 2 },
  { key: "estimated_endurance_h", direction: "higher", weight: 2 },
  { key: "wing_loading_kg_m2", direction: "lower", weight: 1 },
  { key: "defaulted_fields_count", direction: "lower", weight: 2 },
  { key: "missing_metrics_count", direction: "lower", weight: 2 },
];

export type Recommendation = {
  recommendedId: string | null;
  reason: string;
  scores: { id: string; score: number }[];
};

export function recommendVariant(items: CompareItem[]): Recommendation | null {
  if (items.length < 2) return null;

  const allLow = items.every((item) => {
    const c = item.metrics?.confidence;
    return c === "low";
  });
  if (allLow) {
    return { recommendedId: null, reason: "所有方案可信度均较低，暂不推荐", scores: [] };
  }

  const metricsMap = items.map((item) => item.metrics ?? extractCompareMetrics(item));

  const scores = items.map((item, i) => {
    const m = metricsMap[i];
    let score = 0;
    for (const w of WEIGHTS) {
      const val = m?.[w.key];
      if (typeof val !== "number" || !Number.isFinite(val)) continue;
      const allVals = metricsMap
        .map((mm) => mm?.[w.key])
        .filter((v): v is number => typeof v === "number" && Number.isFinite(v));
      if (allVals.length === 0) continue;
      const best = w.direction === "higher" ? Math.max(...allVals) : Math.min(...allVals);
      const worst = w.direction === "higher" ? Math.min(...allVals) : Math.max(...allVals);
      const range = best - worst;
      if (range === 0) continue;
      const normalized = (val - worst) / range;
      score += normalized * w.weight;
    }
    return { id: item.id, score };
  });

  scores.sort((a, b) => b.score - a.score);
  const best = scores[0];
  if (!best || best.score <= 0) {
    return { recommendedId: null, reason: "数据不足，无法推荐", scores };
  }

  const bestItem = items.find((it) => it.id === best.id);
  const label = bestItem?.name ?? best.id;

  return {
    recommendedId: best.id,
    reason: `${label} 综合评分最高（航程、升阻比、默认参数等加权）`,
    scores,
  };
}
