"use client";

import { useEffect, useState } from "react";

export type AdvisoryEntry = {
  entry_id: string;
  topic: string;
  metric: string;
  applies_to?: string[];
  value: number;
  unit: string;
  expected_range: [number, number];
  warn_range?: [number, number] | null;
  status: "pass" | "warn" | "fail" | "info";
  summary_zh: string;
  summary_en?: string;
  citations: string[];
};

type Props = {
  apiBaseUrl: string;
  designId: string | null;
  versionNo?: number;
};

const STATUS_ICON: Record<string, string> = {
  pass: "✓",
  warn: "⚠",
  fail: "✗",
  info: "ⓘ",
};

const STATUS_CLS: Record<string, string> = {
  pass: "design-rule-pass",
  warn: "design-rule-warn",
  fail: "design-rule-fail",
  info: "design-rule-pass",
};

const CATEGORY_OPTIONS: { key: string; label: string }[] = [
  { key: "long_endurance_uav", label: "长航时无人机" },
  { key: "male_uav", label: "MALE 无人机" },
  { key: "fixed_wing_uav", label: "固定翼无人机" },
  { key: "airliner", label: "民航客机" },
  { key: "civil_transport", label: "民用运输" },
  { key: "general_aviation", label: "通用航空" },
  { key: "fighter", label: "战斗机" },
  { key: "stealth_uav", label: "隐身无人机" },
  { key: "stealth_fighter", label: "隐身战斗机" },
];

function fmt(value: number): string {
  if (!Number.isFinite(value)) return "—";
  return Math.abs(value) >= 100
    ? value.toFixed(0)
    : value.toFixed(value < 1 ? 3 : 2);
}

export function ExpertAdvisoryPanel({ apiBaseUrl, designId, versionNo }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [category, setCategory] = useState<string>("long_endurance_uav");
  const [entries, setEntries] = useState<AdvisoryEntry[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!designId || !expanded) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (versionNo) params.set("version_no", String(versionNo));
    if (category) params.set("aircraft_category", category);
    fetch(
      `${apiBaseUrl}/api/expert-knowledge/designs/${encodeURIComponent(designId)}/advisory?${params}`,
    )
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((payload) => {
        if (!cancelled) setEntries(payload.advisory ?? []);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, designId, versionNo, category, expanded]);

  if (!designId) return null;

  const counts = { pass: 0, warn: 0, fail: 0, info: 0 };
  for (const e of entries ?? []) counts[e.status]++;

  return (
    <span className="design-rules">
      <button
        type="button"
        className="design-rules-toggle"
        onClick={() => setExpanded((v) => !v)}
      >
        专家知识参考
        {counts.fail > 0 && (
          <span className="design-rule-pill design-rule-pill-fail">{counts.fail}</span>
        )}
        {counts.warn > 0 && (
          <span className="design-rule-pill design-rule-pill-warn">{counts.warn}</span>
        )}
        {counts.fail === 0 && counts.warn === 0 && (entries?.length ?? 0) > 0 && (
          <span className="design-rule-pill design-rule-pill-pass">{counts.pass}</span>
        )}
        <span className="design-rules-arrow">{expanded ? "▾" : "▸"}</span>
      </button>
      {expanded && (
        <div className="design-rules-list">
          <div className="historical-features">
            <label className="historical-chip" htmlFor="advisory-category">
              对标类别:
            </label>
            <select
              id="advisory-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="historical-chip"
              style={{ background: "transparent" }}
            >
              {CATEGORY_OPTIONS.map((o) => (
                <option key={o.key} value={o.key}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          {loading && <div className="historical-status">加载中...</div>}
          {error && (
            <div className="historical-status historical-status-error">{error}</div>
          )}
          {entries && entries.length === 0 && !loading && (
            <div className="historical-status">该类别下暂无可对照的专家知识条目</div>
          )}
          {entries && entries.length > 0 && (
            <>
              <div className="design-rules-bar">
                <span className="design-rule-pill design-rule-pill-pass">符合 {counts.pass}</span>
                {counts.warn > 0 && (
                  <span className="design-rule-pill design-rule-pill-warn">偏离 {counts.warn}</span>
                )}
                {counts.fail > 0 && (
                  <span className="design-rule-pill design-rule-pill-fail">超出 {counts.fail}</span>
                )}
              </div>
              {entries.map((entry) => (
                <div
                  key={entry.entry_id}
                  className={`design-rule-row ${STATUS_CLS[entry.status]}`}
                >
                  <span className="design-rule-icon">{STATUS_ICON[entry.status]}</span>
                  <span className="design-rule-label" title={entry.topic}>
                    {entry.topic}
                  </span>
                  <span className="design-rule-value">
                    {fmt(entry.value)}
                    {entry.unit ? ` ${entry.unit}` : ""}
                  </span>
                  <span className="design-rule-expected">
                    [{fmt(entry.expected_range[0])} ~ {fmt(entry.expected_range[1])}]
                  </span>
                  <span className="design-rule-msg" title={entry.summary_zh}>
                    {entry.summary_zh}
                    {entry.citations.length > 0 && (
                      <em className="historical-disclaimer" style={{ display: "block", marginTop: 2 }}>
                        参考: {entry.citations.join("; ")}
                      </em>
                    )}
                  </span>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </span>
  );
}
