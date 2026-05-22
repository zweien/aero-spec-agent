import type { CompareItem, CompareMetrics, CompareMetricSource, MetricConfidence } from "./types";

type PerfEstimate = { estimate_id: string; value: number };
type DesignMetrics = Record<string, unknown>;

function sourceFor(dmValue: unknown, estValue: unknown, clientValue: unknown): CompareMetricSource {
  if (dmValue != null) return "backend_design_metrics";
  if (estValue != null) return "performance_estimate";
  if (clientValue != null) return "client_heuristic";
  return "missing";
}

/**
 * Extract CompareMetrics from an item's spec, validationReport, and defaultedFields.
 * Priority: validationReport.design_metrics (backend) > performance_estimate > client-side computation.
 */
export function extractCompareMetrics(item: CompareItem): CompareMetrics {
  const spec = item.spec ?? {};
  const vr = (item.validationReport ?? {}) as Record<string, unknown>;
  const dm = (vr.design_metrics ?? null) as DesignMetrics | null;
  const perfEstimates = ((vr as Record<string, unknown>)?.performance_estimate as Record<string, unknown>)?.estimates as PerfEstimate[] | undefined;
  const defaultedFields = item.defaultedFields;

  const findEst = (id: string) => perfEstimates?.find((e) => e.estimate_id === id)?.value;

  const sources: Record<string, CompareMetricSource> = {};

  // wingspan_m — backend > spec
  const dmWingspan = dm?.wingspan_m as number | undefined;
  const wingspan_m =
    dmWingspan ??
    numVal(spec, "wing.span") ??
    numVal(spec, "wingspan");
  sources.wingspan_m = sourceFor(dmWingspan, undefined, wingspan_m !== dmWingspan ? wingspan_m : undefined);

  // fuselage_length_m
  const dmFuselage = dm?.fuselage_length_m as number | undefined;
  const fuselage_length_m =
    dmFuselage ??
    numVal(spec, "fuselage.length");
  sources.fuselage_length_m = sourceFor(dmFuselage, undefined, fuselage_length_m !== dmFuselage ? fuselage_length_m : undefined);

  // wing_area_m2 — backend > estimate > trapezoidal
  const dmWingArea = dm?.wing_area_m2 as number | undefined;
  const estWingArea = findEst("wing_area_m2") ?? findEst("wing_area");
  let wing_area_m2 = dmWingArea ?? estWingArea;
  let clientWingArea: number | undefined;
  if (wing_area_m2 == null) {
    const rootChord = numVal(spec, "wing.root_chord");
    const tipChord = numVal(spec, "wing.tip_chord");
    if (wingspan_m != null && rootChord != null && tipChord != null) {
      clientWingArea = wingspan_m * (rootChord + tipChord) / 2;
      wing_area_m2 = clientWingArea;
    }
  }
  sources.wing_area_m2 = sourceFor(dmWingArea, estWingArea, clientWingArea);

  // aspect_ratio — backend > estimate > compute
  const dmAspectRatio = dm?.aspect_ratio as number | undefined;
  const estAspectRatio = findEst("aspect_ratio_perf");
  let aspect_ratio = dmAspectRatio ?? estAspectRatio;
  let clientAspectRatio: number | undefined;
  if (aspect_ratio == null && wingspan_m != null && wing_area_m2 != null && wing_area_m2 > 0) {
    clientAspectRatio = (wingspan_m * wingspan_m) / wing_area_m2;
    aspect_ratio = clientAspectRatio;
  }
  sources.aspect_ratio = sourceFor(dmAspectRatio, estAspectRatio, clientAspectRatio);

  // estimated_lift_to_drag — backend > estimate > heuristic
  const dmLD = dm?.estimated_lift_to_drag as number | undefined;
  const estLD = findEst("ld_cruise");
  let estimated_lift_to_drag = dmLD ?? estLD;
  let clientLD: number | undefined;
  if (estimated_lift_to_drag == null && aspect_ratio != null) {
    clientLD = clamp(8 + aspect_ratio * 0.7, 8, 22);
    estimated_lift_to_drag = clientLD;
  }
  sources.estimated_lift_to_drag = sourceFor(dmLD, estLD, clientLD);

  // estimated_range_km / endurance_h — backend > estimate
  const dmRange = dm?.estimated_range_km as number | undefined;
  const estRange = findEst("range_est");
  const estimated_range_km = dmRange ?? estRange;
  sources.estimated_range_km = sourceFor(dmRange, estRange, undefined);

  const dmEndurance = dm?.estimated_endurance_h as number | undefined;
  const estEndurance = findEst("endurance_est");
  const estimated_endurance_h = dmEndurance ?? estEndurance;
  sources.estimated_endurance_h = sourceFor(dmEndurance, estEndurance, undefined);

  // wing_loading_kg_m2 — backend > estimate
  const dmWingLoading = dm?.wing_loading_kg_m2 as number | undefined;
  const estWingLoading = findEst("wing_loading_mtow");
  const wing_loading_kg_m2 = dmWingLoading ?? estWingLoading;
  sources.wing_loading_kg_m2 = sourceFor(dmWingLoading, estWingLoading, undefined);

  // defaulted_fields_count — handle null array
  const defaulted_fields_count = Array.isArray(defaultedFields) ? defaultedFields.length : 0;

  // missing_metrics_count (core 7 metrics)
  const coreMetrics = [wingspan_m, fuselage_length_m, wing_area_m2, aspect_ratio, estimated_lift_to_drag, estimated_range_km, estimated_endurance_h];
  const missing_metrics_count = coreMetrics.filter((v) => v == null).length;

  // risk_level — backend > client heuristic
  const dmRisk = dm?.risk_level as CompareMetrics["risk_level"] | undefined;
  let risk_level: CompareMetrics["risk_level"] = dmRisk ?? "low";
  if (!dmRisk) {
    if (defaulted_fields_count >= 5) risk_level = "medium";
    else if (aspect_ratio != null && aspect_ratio < 5) risk_level = "medium";
    else if (missing_metrics_count >= 5) risk_level = "medium";
  }

  // Confidence
  const backendCount = Object.values(sources).filter((s) => s === "backend_design_metrics").length;
  const missingCount = Object.values(sources).filter((s) => s === "missing").length;
  let confidence: MetricConfidence;
  if (backendCount >= 5 && missingCount <= 1) {
    confidence = "high";
  } else if (backendCount >= 3 || missingCount <= 3) {
    confidence = "medium";
  } else {
    confidence = "low";
  }

  // Warnings
  const warnings: string[] = [];
  if (missing_metrics_count > 0) {
    warnings.push(`${missing_metrics_count} 项核心指标缺失`);
  }
  if (defaulted_fields_count >= 3) {
    warnings.push(`${defaulted_fields_count} 项参数由系统默认补全`);
  }
  if (confidence === "low") {
    warnings.push("整体置信度较低，建议谨慎参考");
  }

  return {
    wingspan_m,
    fuselage_length_m,
    wing_area_m2,
    aspect_ratio,
    estimated_lift_to_drag,
    estimated_range_km,
    estimated_endurance_h,
    wing_loading_kg_m2,
    risk_level,
    defaulted_fields_count,
    missing_metrics_count,
    metric_sources: sources,
    confidence,
    warnings,
  };
}

export const SOURCE_LABELS: Record<CompareMetricSource, string> = {
  backend_design_metrics: "后端估算",
  performance_estimate: "性能估算",
  client_heuristic: "临时估算",
  missing: "暂无",
};

/**
 * Traverse a dotted path and return the numeric value.
 * Handles both `obj.a.b = 5` and `obj.a.b = { value: 5 }`.
 */
function numVal(obj: Record<string, unknown>, dottedPath: string): number | undefined {
  const parts = dottedPath.split(".");
  let cur: unknown = obj;
  for (const p of parts) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = (cur as Record<string, unknown>)[p];
  }
  if (typeof cur === "number") return cur;
  if (cur != null && typeof cur === "object") {
    const v = (cur as Record<string, unknown>).value;
    if (typeof v === "number") return v;
  }
  return undefined;
}

function clamp(val: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, val));
}
