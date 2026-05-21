import type { CompareItem, CompareMetrics } from "./types";

type PerfEstimate = { estimate_id: string; value: number };

/**
 * Extract CompareMetrics from an item's spec, validationReport, and defaultedFields.
 * Purely client-side — no backend calls.
 */
export function extractCompareMetrics(item: CompareItem): CompareMetrics {
  const spec = item.spec ?? {};
  const vr = (item.validationReport ?? {}) as Record<string, unknown>;
  const perfEstimates = ((vr as Record<string, unknown>)?.performance_estimate as Record<string, unknown>)?.estimates as PerfEstimate[] | undefined;
  const defaultedFields = item.defaultedFields;

  const findEst = (id: string) => perfEstimates?.find((e) => e.estimate_id === id)?.value;

  // wingspan_m — try multiple paths
  const wingspan_m =
    numVal(spec, "wing.span") ??
    numVal(spec, "wingspan");

  // fuselage_length_m
  const fuselage_length_m = numVal(spec, "fuselage.length");

  // wing_area_m2 — prefer estimate, then fallback to trapezoidal
  let wing_area_m2 = findEst("wing_area_m2") ?? findEst("wing_area");
  if (wing_area_m2 == null) {
    const rootChord = numVal(spec, "wing.root_chord");
    const tipChord = numVal(spec, "wing.tip_chord");
    if (wingspan_m != null && rootChord != null && tipChord != null) {
      wing_area_m2 = wingspan_m * (rootChord + tipChord) / 2;
    }
  }

  // aspect_ratio — prefer estimate, then compute from span/area
  let aspect_ratio = findEst("aspect_ratio_perf");
  if (aspect_ratio == null && wingspan_m != null && wing_area_m2 != null && wing_area_m2 > 0) {
    aspect_ratio = (wingspan_m * wingspan_m) / wing_area_m2;
  }

  // estimated_lift_to_drag — prefer estimate, fallback to heuristic
  let estimated_lift_to_drag = findEst("ld_cruise");
  if (estimated_lift_to_drag == null && aspect_ratio != null) {
    estimated_lift_to_drag = clamp(8 + aspect_ratio * 0.7, 8, 22);
  }

  // estimated_range_km / endurance_h
  const estimated_range_km = findEst("range_est");
  const estimated_endurance_h = findEst("endurance_est");

  // wing_loading_kg_m2
  const wing_loading_kg_m2 = findEst("wing_loading_mtow");

  // defaulted_fields_count — handle null array
  const defaulted_fields_count = Array.isArray(defaultedFields) ? defaultedFields.length : 0;

  // missing_metrics_count (core 7 metrics)
  const coreMetrics = [wingspan_m, fuselage_length_m, wing_area_m2, aspect_ratio, estimated_lift_to_drag, estimated_range_km, estimated_endurance_h];
  const missing_metrics_count = coreMetrics.filter((v) => v == null).length;

  // risk_level
  let risk_level: CompareMetrics["risk_level"] = "low";
  if (defaulted_fields_count >= 5) risk_level = "medium";
  else if (aspect_ratio != null && aspect_ratio < 5) risk_level = "medium";
  else if (missing_metrics_count >= 5) risk_level = "medium";

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
