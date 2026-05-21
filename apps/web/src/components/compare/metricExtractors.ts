import type { CompareItem, CompareMetrics } from "./types";

type PerfEstimate = { estimate_id: string; value: number };
type DesignMetrics = Record<string, unknown>;

/**
 * Extract CompareMetrics from an item's spec, validationReport, and defaultedFields.
 * Priority: validationReport.design_metrics (backend) > client-side computation.
 */
export function extractCompareMetrics(item: CompareItem): CompareMetrics {
  const spec = item.spec ?? {};
  const vr = (item.validationReport ?? {}) as Record<string, unknown>;
  const dm = (vr.design_metrics ?? null) as DesignMetrics | null;
  const perfEstimates = ((vr as Record<string, unknown>)?.performance_estimate as Record<string, unknown>)?.estimates as PerfEstimate[] | undefined;
  const defaultedFields = item.defaultedFields;

  const findEst = (id: string) => perfEstimates?.find((e) => e.estimate_id === id)?.value;

  // wingspan_m — backend > spec
  const wingspan_m =
    (dm?.wingspan_m as number | undefined) ??
    numVal(spec, "wing.span") ??
    numVal(spec, "wingspan");

  // fuselage_length_m
  const fuselage_length_m =
    (dm?.fuselage_length_m as number | undefined) ??
    numVal(spec, "fuselage.length");

  // wing_area_m2 — backend > estimate > trapezoidal
  let wing_area_m2 =
    (dm?.wing_area_m2 as number | undefined) ??
    findEst("wing_area_m2") ?? findEst("wing_area");
  if (wing_area_m2 == null) {
    const rootChord = numVal(spec, "wing.root_chord");
    const tipChord = numVal(spec, "wing.tip_chord");
    if (wingspan_m != null && rootChord != null && tipChord != null) {
      wing_area_m2 = wingspan_m * (rootChord + tipChord) / 2;
    }
  }

  // aspect_ratio — backend > estimate > compute
  let aspect_ratio =
    (dm?.aspect_ratio as number | undefined) ??
    findEst("aspect_ratio_perf");
  if (aspect_ratio == null && wingspan_m != null && wing_area_m2 != null && wing_area_m2 > 0) {
    aspect_ratio = (wingspan_m * wingspan_m) / wing_area_m2;
  }

  // estimated_lift_to_drag — backend > estimate > heuristic
  let estimated_lift_to_drag =
    (dm?.estimated_lift_to_drag as number | undefined) ??
    findEst("ld_cruise");
  if (estimated_lift_to_drag == null && aspect_ratio != null) {
    estimated_lift_to_drag = clamp(8 + aspect_ratio * 0.7, 8, 22);
  }

  // estimated_range_km / endurance_h — backend > estimate
  const estimated_range_km =
    (dm?.estimated_range_km as number | undefined) ??
    findEst("range_est");

  const estimated_endurance_h =
    (dm?.estimated_endurance_h as number | undefined) ??
    findEst("endurance_est");

  // wing_loading_kg_m2 — backend > estimate
  const wing_loading_kg_m2 =
    (dm?.wing_loading_kg_m2 as number | undefined) ??
    findEst("wing_loading_mtow");

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
  };
}

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
