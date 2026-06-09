"use client";

import { useEffect, useState } from "react";

export type HistoricalMatch = {
  aircraft_id: string;
  name: string;
  role: string;
  layout: string;
  similarity: number;
  distance: number;
  deltas: Record<string, number>;
  reference: Record<string, unknown>;
};

export type HistoricalComparePayload = {
  spec_features: Record<string, number>;
  matches: HistoricalMatch[];
  database_size: number;
  design_id?: string;
  version_no?: number;
};

type Props = {
  apiBaseUrl: string;
  designId: string | null;
  versionNo?: number;
};

const FEATURE_LABELS: Record<string, string> = {
  wingspan_m: "翼展 (m)",
  length_m: "机身长 (m)",
  mtow_kg: "MTOW (kg)",
  payload_kg: "载荷 (kg)",
  cruise_speed_kmh: "巡航速度 (km/h)",
  range_km: "航程 (km)",
  aspect_ratio: "展弦比",
};

function fmt(value: number, fractionDigits = 1): string {
  if (!Number.isFinite(value)) return "—";
  return value.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: fractionDigits,
  });
}

function similarityPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function similarityClass(value: number): string {
  if (value >= 0.8) return "historical-bar-high";
  if (value >= 0.5) return "historical-bar-mid";
  return "historical-bar-low";
}

export function HistoricalComparePanel({ apiBaseUrl, designId, versionNo }: Props) {
  const [data, setData] = useState<HistoricalComparePayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!designId || !expanded) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    const versionQuery = versionNo ? `?version_no=${versionNo}` : "";
    fetch(`${apiBaseUrl}/api/designs/${encodeURIComponent(designId)}/historical-compare${versionQuery}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((payload) => {
        if (!cancelled) setData(payload);
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
  }, [apiBaseUrl, designId, versionNo, expanded]);

  if (!designId) return null;

  return (
    <span className="design-rules">
      <button
        type="button"
        className="design-rules-toggle"
        onClick={() => setExpanded((v) => !v)}
      >
        历史型号比对
        {data?.matches?.length ? (
          <span className="design-rule-pill design-rule-pill-pass">
            Top {data.matches.length}
          </span>
        ) : null}
        <span className="design-rules-arrow">{expanded ? "▾" : "▸"}</span>
      </button>
      {expanded && (
        <div className="design-rules-list">
          {loading && <div className="historical-status">加载中...</div>}
          {error && <div className="historical-status historical-status-error">{error}</div>}
          {data && data.matches && data.matches.length === 0 && (
            <div className="historical-status">暂无可比对的历史型号 (spec 缺少关键参数)</div>
          )}
          {data && data.matches && data.matches.length > 0 && (
            <>
              <div className="historical-features">
                {Object.entries(data.spec_features).map(([k, v]) => (
                  <span key={k} className="historical-chip">
                    {FEATURE_LABELS[k] ?? k}: <strong>{fmt(v, 2)}</strong>
                  </span>
                ))}
              </div>
              <table className="historical-table">
                <thead>
                  <tr>
                    <th>型号</th>
                    <th>用途</th>
                    <th>布局</th>
                    <th>相似度</th>
                    <th>翼展 / 长度</th>
                    <th>MTOW / 载荷</th>
                  </tr>
                </thead>
                <tbody>
                  {data.matches.map((m) => {
                    const ref = m.reference as Record<string, number | string>;
                    return (
                      <tr key={m.aircraft_id}>
                        <td title={String(ref.note ?? "")}>{m.name}</td>
                        <td>{m.role}</td>
                        <td>{m.layout}</td>
                        <td>
                          <div className="historical-bar-track">
                            <div
                              className={`historical-bar ${similarityClass(m.similarity)}`}
                              style={{ width: `${m.similarity * 100}%` }}
                            />
                          </div>
                          <span className="historical-bar-label">{similarityPct(m.similarity)}</span>
                        </td>
                        <td>
                          {fmt(Number(ref.wingspan_m))} / {fmt(Number(ref.length_m))} m
                        </td>
                        <td>
                          {fmt(Number(ref.mtow_kg), 0)} / {fmt(Number(ref.payload_kg), 0)} kg
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div className="historical-disclaimer">
                数据为公开来源,仅用于概念阶段方案对标,不代表工程设计结论。
              </div>
            </>
          )}
        </div>
      )}
    </span>
  );
}
