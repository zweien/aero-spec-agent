"use client";

import { type JSX } from "react";
import type { CompareItem, CompareSource } from "./types";

export type CompareItemCardProps = {
  item: CompareItem;
  onRemove: (id: string) => void;
  onViewModel?: (item: CompareItem) => void;
  onSetCurrent?: (item: CompareItem) => void;
};

const SOURCE_LABELS: Record<CompareSource, { text: string; color: string; bg: string }> = {
  version: { text: "Version", color: "var(--text-dim)", bg: "var(--bg-surface)" },
  "deep-design-variant": { text: "Deep Design", color: "var(--accent)", bg: "var(--accent-bg)" },
  recommended: { text: "推荐方案", color: "#fff", bg: "var(--accent)" },
};

export function CompareItemCard({ item, onRemove, onViewModel, onSetCurrent }: CompareItemCardProps): JSX.Element {
  const src = SOURCE_LABELS[item.source] ?? SOURCE_LABELS.version;
  const dfCount = item.defaultedFields?.length ?? 0;

  return (
    <div
      style={{
        border: "1px solid var(--border-default)",
        borderRadius: "var(--radius)",
        padding: 10,
        background: "var(--bg-elevated)",
        minWidth: 0,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
          {item.name ?? `v${item.versionNo}`}
        </span>
        <span
          style={{
            fontSize: 9,
            fontWeight: 600,
            color: src.color,
            background: src.bg,
            border: item.source === "recommended" ? "none" : "1px solid var(--border-default)",
            borderRadius: 3,
            padding: "1px 5px",
            letterSpacing: 0.3,
            flexShrink: 0,
          }}
        >
          {src.text}
        </span>
        <span style={{ fontSize: 10, color: "var(--text-muted)", marginLeft: "auto" }}>
          v{item.versionNo}
        </span>
      </div>

      {/* Defaulted fields hint */}
      {dfCount > 0 && (
        <div
          style={{
            fontSize: 11,
            color: dfCount >= 3 ? "var(--warning, #ca8a04)" : "var(--text-muted)",
            marginBottom: 6,
          }}
        >
          {dfCount >= 3 ? `默认补全较多 ${dfCount} 项` : `默认补全 ${dfCount} 项`}
        </div>
      )}
      {dfCount === 0 && (
        <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6 }}>
          无默认补全
        </div>
      )}

      {/* Risk badge */}
      {item.metrics?.risk_level && (
        <div style={{ marginBottom: 8 }}>
          <RiskBadge level={item.metrics.risk_level} />
        </div>
      )}

      {/* Actions */}
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {onViewModel && (
          <SmallBtn label="查看模型" onClick={() => onViewModel(item)} />
        )}
        {onSetCurrent && (
          <SmallBtn label="设为当前" onClick={() => onSetCurrent(item)} />
        )}
        <SmallBtn label="移除" onClick={() => onRemove(item.id)} />
      </div>
    </div>
  );
}

function RiskBadge({ level }: { level: string }): JSX.Element {
  const cfg: Record<string, { bg: string; color: string; text: string }> = {
    low: { bg: "rgba(34,197,94,0.1)", color: "var(--success, #16a34a)", text: "风险：低" },
    medium: { bg: "rgba(234,179,8,0.1)", color: "var(--warning, #ca8a04)", text: "风险：中" },
    high: { bg: "rgba(239,68,68,0.1)", color: "var(--error, #dc2626)", text: "风险：高" },
    unknown: { bg: "var(--bg-surface)", color: "var(--text-muted)", text: "风险：未知" },
  };
  const c = cfg[level] ?? cfg.unknown;
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 500,
        color: c.color,
        background: c.bg,
        borderRadius: 3,
        padding: "1px 6px",
      }}
    >
      {c.text}
    </span>
  );
}

function SmallBtn({ label, onClick }: { label: string; onClick: () => void }): JSX.Element {
  return (
    <button
      onClick={onClick}
      style={{
        fontSize: 10,
        padding: "3px 7px",
        background: "transparent",
        border: "1px solid var(--border-default)",
        borderRadius: "var(--radius-sm)",
        color: "var(--text-dim)",
        cursor: "pointer",
      }}
    >
      {label}
    </button>
  );
}
