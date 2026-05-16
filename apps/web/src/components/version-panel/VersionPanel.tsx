import { useState } from "react";

import type { DesignRuleEntry, PerformanceEstimateEntry, VspaeroAnalysisEntry } from "@/app/page";

type VersionPanelProps = {
  designRules?: DesignRuleEntry[] | null;
  perfEstimates?: PerformanceEstimateEntry[] | null;
  aeroAnalysis?: VspaeroAnalysisEntry | null;
};

export function VersionPanel({
  designRules,
  perfEstimates,
  aeroAnalysis,
}: VersionPanelProps) {
  const hasContent = (designRules && designRules.length > 0) || (perfEstimates && perfEstimates.length > 0) || aeroAnalysis;
  if (!hasContent) return null;

  return (
    <section className="bottom-panel">
      {designRules && designRules.length > 0 && (
        <DesignRulesSummary rules={designRules} />
      )}
      {perfEstimates && perfEstimates.length > 0 && (
        <PerformanceEstimateSummary estimates={perfEstimates} />
      )}
      {aeroAnalysis && <VspaeroSummary analysis={aeroAnalysis} />}
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
