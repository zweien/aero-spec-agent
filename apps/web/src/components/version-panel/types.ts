import type { DesignRuleEntry, ExtendedMetricEntry, PerformanceEstimateEntry, VspaeroAnalysisEntry } from "@/app/page";

export type VersionResponse = {
  files: string[];
  validation_report?: {
    spec_echo?: Record<string, unknown>;
    design_rules?: {
      rules: DesignRuleEntry[];
      summary: Record<string, number>;
    };
    performance_estimate?: {
      estimates: PerformanceEstimateEntry[];
      summary: Record<string, number>;
    };
    extended_metrics?: {
      metrics: ExtendedMetricEntry[];
      summary: Record<string, number>;
    };
    vspaero_analysis?: VspaeroAnalysisEntry;
  };
};
