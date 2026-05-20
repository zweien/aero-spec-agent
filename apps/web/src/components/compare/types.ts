export type CompareSource = "version" | "deep-design-variant" | "recommended";

export type DefaultedField = {
  path: string;
  label: string;
  value: number | string;
  unit?: string;
  reason: string;
};

export type CompareMetrics = {
  wingspan_m?: number;
  fuselage_length_m?: number;
  wing_area_m2?: number;
  aspect_ratio?: number;
  estimated_lift_to_drag?: number;
  estimated_range_km?: number;
  estimated_endurance_h?: number;
  wing_loading_kg_m2?: number;
  risk_level?: "low" | "medium" | "high" | "unknown";
  defaulted_fields_count?: number;
  missing_metrics_count?: number;
};

export type CompareItem = {
  id: string;
  designId: string;
  versionNo: number;
  name?: string;
  source: CompareSource;
  spec?: Record<string, unknown>;
  metrics?: CompareMetrics;
  artifacts?: string[];
  defaultedFields?: DefaultedField[];
  validationReport?: Record<string, unknown>;
};
