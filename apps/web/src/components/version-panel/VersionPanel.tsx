"use client";

import { useState } from "react";

import type { DesignRuleEntry, PerformanceEstimateEntry, VspaeroAnalysisEntry } from "@/app/page";
import { VersionCompare } from "./VersionCompare";
import { AddToCompareButton } from "@/components/compare/AddToCompareButton";
import type { CompareItem } from "@/components/compare/types";

type VersionResponse = {
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
    vspaero_analysis?: VspaeroAnalysisEntry;
  };
};

type VersionPanelProps = {
  designRules?: DesignRuleEntry[] | null;
  perfEstimates?: PerformanceEstimateEntry[] | null;
  aeroAnalysis?: VspaeroAnalysisEntry | null;
  versionList?: number[];
  currentVersionNo?: number;
  designId?: string | null;
  onCompare?: (v1: number, v2: number) => void;
  onCancelCompare?: () => void;
  onSelectVersion?: (versionNo: number) => void;
  compareVersions?: [number, number] | null;
  compareData?: [VersionResponse, VersionResponse] | null;
  isInGlobalCompare?: (id: string) => boolean;
  onAddToGlobalCompare?: (item: CompareItem) => void;
};

export function VersionPanel({
  designRules,
  perfEstimates,
  aeroAnalysis,
  versionList,
  currentVersionNo,
  designId,
  onCompare,
  onCancelCompare,
  onSelectVersion,
  compareVersions,
  compareData,
  isInGlobalCompare,
  onAddToGlobalCompare,
}: VersionPanelProps) {
  const [compareMode, setCompareMode] = useState(false);
  const [selectedFirst, setSelectedFirst] = useState<number | null>(null);

  const hasContent = (designRules && designRules.length > 0) || (perfEstimates && perfEstimates.length > 0) || aeroAnalysis;
  const hasVersions = versionList && versionList.length > 0;

  if (!hasContent && !hasVersions) return null;

  const handleCompareClick = () => {
    setCompareMode(true);
    setSelectedFirst(null);
  };

  const handleVersionClick = (v: number) => {
    if (compareMode) {
      if (selectedFirst === null) {
        setSelectedFirst(v);
      } else if (v !== selectedFirst) {
        onCompare?.(selectedFirst, v);
        setCompareMode(false);
        setSelectedFirst(null);
      }
    } else {
      onSelectVersion?.(v);
    }
  };

  const handleCancel = () => {
    setCompareMode(false);
    setSelectedFirst(null);
    onCancelCompare?.();
  };

  const isComparing = compareVersions != null && compareData != null;

  return (
    <section className="bottom-panel">
      {hasVersions && (
        <div className="version-selector">
          <div className="version-pills">
            {versionList!.map((v) => {
              const isCurrent = v === currentVersionNo;
              const isSelected = v === selectedFirst;
              const compareId = `${designId ?? "unknown"}-v${v}`;
              return (
                <span key={v} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                  <button
                    type="button"
                    className={`version-pill ${isCurrent ? "version-pill-active" : ""} ${isSelected ? "version-pill-selected" : ""}`}
                    onClick={() => handleVersionClick(v)}
                  >
                    v{v}
                  </button>
                  {onAddToGlobalCompare && (
                    <AddToCompareButton
                      isAdded={!!isInGlobalCompare?.(compareId)}
                      onAdd={() => onAddToGlobalCompare({
                        id: compareId,
                        designId: designId ?? "",
                        versionNo: v,
                        name: `v${v}`,
                        source: "version",
                      })}
                    />
                  )}
                </span>
              );
            })}
          </div>
          <div className="version-actions">
            {compareMode ? (
              <>
                <span className="compare-hint">
                  {selectedFirst == null ? "选择版本 A" : `已选 v${selectedFirst}，选择版本 B`}
                </span>
                <button type="button" className="compare-cancel-btn" onClick={handleCancel}>
                  取消
                </button>
              </>
            ) : (
              versionList!.length >= 2 && (
                <button type="button" className="compare-btn" onClick={handleCompareClick}>
                  对比
                </button>
              )
            )}
          </div>
        </div>
      )}

      {isComparing && compareData ? (
        <VersionCompare
          v1No={compareVersions[0]}
          v2No={compareVersions[1]}
          data={compareData}
        />
      ) : (
        <>
          {designRules && designRules.length > 0 && (
            <DesignRulesSummary rules={designRules} />
          )}
          {perfEstimates && perfEstimates.length > 0 && (
            <PerformanceEstimateSummary estimates={perfEstimates} />
          )}
          {aeroAnalysis && <VspaeroSummary analysis={aeroAnalysis} />}
        </>
      )}

      {isComparing && (
        <button type="button" className="compare-cancel-btn compare-exit-btn" onClick={handleCancel}>
          退出对比
        </button>
      )}
    </section>
  );
}

function DesignRulesSummary({ rules }: { rules: DesignRuleEntry[] }) {
  const [expanded, setExpanded] = useState(false);
  const counts = { pass: 0, warn: 0, fail: 0, skip: 0 };
  for (const r of rules) {
    counts[r.status]++;
  }

  return (
    <span className="design-rules">
      <button
        type="button"
        className="design-rules-toggle"
        onClick={() => setExpanded(!expanded)}
      >
        设计检查
        {counts.fail > 0 && (
          <span className="design-rule-pill design-rule-pill-fail">
            {counts.fail}
          </span>
        )}
        {counts.warn > 0 && (
          <span className="design-rule-pill design-rule-pill-warn">
            {counts.warn}
          </span>
        )}
        {counts.fail === 0 && counts.warn === 0 && (
          <span className="design-rule-pill design-rule-pill-pass">
            {counts.pass}
          </span>
        )}
        <span className="design-rules-arrow">
          {expanded ? "▾" : "▸"}
        </span>
      </button>
      {expanded && (
        <div className="design-rules-list">
          <div className="design-rules-bar">
            <span className="design-rule-pill design-rule-pill-pass">
              通过 {counts.pass}
            </span>
            {counts.warn > 0 && (
              <span className="design-rule-pill design-rule-pill-warn">
                警告 {counts.warn}
              </span>
            )}
            {counts.fail > 0 && (
              <span className="design-rule-pill design-rule-pill-fail">
                失败 {counts.fail}
              </span>
            )}
            {counts.skip > 0 && (
              <span className="design-rule-pill design-rule-pill-skip">
                跳过 {counts.skip}
              </span>
            )}
          </div>
          {rules.map((r) => (
            <div key={r.rule_id} className={`design-rule-row design-rule-${r.status}`}>
              <span className="design-rule-icon">{STATUS_ICON[r.status]}</span>
              <span className="design-rule-label">{r.label}</span>
              <span className="design-rule-value">
                {typeof r.value === "number" ? r.value : r.value}
              </span>
              <span className="design-rule-expected">{r.expected}</span>
              <span className="design-rule-msg">{r.message}</span>
            </div>
          ))}
        </div>
      )}
    </span>
  );
}

const STATUS_ICON: Record<string, string> = {
  pass: "✓",
  warn: "⚠",
  fail: "✗",
  skip: "—",
};

const CONFIDENCE_ICON: Record<string, string> = {
  high: "●",
  medium: "◐",
  low: "○",
};

const PERF_STATUS_ICON: Record<string, string> = {
  reasonable: "✓",
  warning: "⚠",
  unusual: "✗",
};

function PerformanceEstimateSummary({ estimates }: { estimates: PerformanceEstimateEntry[] }) {
  const [expanded, setExpanded] = useState(false);
  const counts = { reasonable: 0, warning: 0, unusual: 0 };
  for (const e of estimates) {
    counts[e.status]++;
  }

  return (
    <span className="design-rules">
      <button
        type="button"
        className="design-rules-toggle"
        onClick={() => setExpanded(!expanded)}
      >
        性能估算
        {counts.unusual > 0 && (
          <span className="design-rule-pill design-rule-pill-fail">
            {counts.unusual}
          </span>
        )}
        {counts.warning > 0 && (
          <span className="design-rule-pill design-rule-pill-warn">
            {counts.warning}
          </span>
        )}
        {counts.unusual === 0 && counts.warning === 0 && (
          <span className="design-rule-pill design-rule-pill-pass">
            {counts.reasonable}
          </span>
        )}
        <span className="design-rules-arrow">
          {expanded ? "▾" : "▸"}
        </span>
      </button>
      {expanded && (
        <div className="design-rules-list">
          <div className="design-rules-bar">
            <span className="design-rule-pill design-rule-pill-pass">
              合理 {counts.reasonable}
            </span>
            {counts.warning > 0 && (
              <span className="design-rule-pill design-rule-pill-warn">
                偏离 {counts.warning}
              </span>
            )}
            {counts.unusual > 0 && (
              <span className="design-rule-pill design-rule-pill-fail">
                异常 {counts.unusual}
              </span>
            )}
          </div>
          {estimates.map((e) => (
            <div key={e.estimate_id} className={`design-rule-row design-rule-${e.status === "warning" ? "warn" : e.status === "unusual" ? "fail" : "pass"}`}>
              <span className="design-rule-icon">{PERF_STATUS_ICON[e.status]}</span>
              <span className="design-rule-label">{e.label}</span>
              <span className="design-rule-value">
                {typeof e.value === "number" ? (Number.isInteger(e.value) ? e.value : e.value.toFixed(2)) : e.value}
                {e.unit ? ` ${e.unit}` : ""}
              </span>
              <span className="design-rule-expected" title={e.method}>
                {CONFIDENCE_ICON[e.confidence]} {e.typical_range}
              </span>
              <span className="design-rule-msg">{e.message}</span>
            </div>
          ))}
        </div>
      )}
    </span>
  );
}

function VspaeroSummary({ analysis }: { analysis: VspaeroAnalysisEntry }) {
  const [expanded, setExpanded] = useState(false);
  const isOk = analysis.status === "success";
  const methodLabel = analysis.method === "VSPAERO_panel" ? "面元法" : analysis.method === "fake_vspaero" ? "模拟" : analysis.method;

  return (
    <span className="design-rules">
      <button
        type="button"
        className="design-rules-toggle"
        onClick={() => setExpanded(!expanded)}
      >
        气动分析
        <span className={`design-rule-pill ${isOk ? "design-rule-pill-pass" : "design-rule-pill-fail"}`}>
          {isOk ? "✓" : "✗"} {methodLabel}
        </span>
        <span className="design-rules-arrow">
          {expanded ? "▾" : "▸"}
        </span>
      </button>
      {expanded && (
        <div className="design-rules-list">
          {analysis.error_message && (
            <div className="design-rule-row design-rule-fail">
              <span className="design-rule-icon">✗</span>
              <span className="design-rule-msg">{analysis.error_message}</span>
            </div>
          )}
          {isOk && (
            <>
              <div className="design-rules-bar">
                <span className="aero-metric">
                  L/D <strong>{analysis.optimal_ld.toFixed(1)}</strong>
                </span>
                <span className="aero-metric">
                  CL<sub>opt</sub> <strong>{analysis.optimal_cl.toFixed(3)}</strong>
                </span>
                <span className="aero-metric">
                  α<sub>opt</sub> <strong>{analysis.optimal_alpha.toFixed(1)}°</strong>
                </span>
                {analysis.cd0_estimate != null && (
                  <span className="aero-metric">
                    CD₀ <strong>{analysis.cd0_estimate.toFixed(4)}</strong>
                  </span>
                )}
                {analysis.cl_alpha != null && (
                  <span className="aero-metric">
                    CL<sub>α</sub> <strong>{analysis.cl_alpha.toFixed(3)}/rad</strong>
                  </span>
                )}
              </div>
              {analysis.alpha_sweep.length > 0 && (
                <table className="aero-sweep-table">
                  <thead>
                    <tr>
                      <th>α (°)</th>
                      <th>CL</th>
                      <th>CD</th>
                      <th>CM</th>
                      <th>L/D</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analysis.alpha_sweep.map((pt, i) => (
                      <tr key={i} className={pt.alpha === analysis.optimal_alpha ? "aero-optimal" : ""}>
                        <td>{pt.alpha.toFixed(1)}</td>
                        <td>{pt.cl.toFixed(4)}</td>
                        <td>{pt.cd.toFixed(5)}</td>
                        <td>{pt.cm.toFixed(4)}</td>
                        <td>{pt.cd > 1e-6 ? (pt.cl / pt.cd).toFixed(1) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </div>
      )}
    </span>
  );
}
