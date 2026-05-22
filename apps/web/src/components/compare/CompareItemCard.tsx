"use client";

import { type JSX } from "react";
import type { CompareItem, CompareSource } from "./types";

export type CompareItemCardProps = {
  item: CompareItem;
  onRemove: (id: string) => void;
  onViewModel?: (item: CompareItem) => void;
  onSetCurrent?: (item: CompareItem) => void;
};

const SOURCE_LABELS: Record<CompareSource, string> = {
  version: "Version",
  "deep-design-variant": "Deep Design",
  recommended: "推荐方案",
};

export function CompareItemCard({ item, onRemove, onViewModel, onSetCurrent }: CompareItemCardProps): JSX.Element {
  const sourceLabel = SOURCE_LABELS[item.source] ?? SOURCE_LABELS.version;
  const dfCount = item.defaultedFields?.length ?? 0;

  return (
    <div className="compare-item-card">
      <div className="compare-item-card-header">
        <span className="compare-item-name">
          {item.name ?? `v${item.versionNo}`}
        </span>
        <span className={`compare-source-pill compare-source-${item.source}`}>
          {sourceLabel}
        </span>
        <span className="compare-item-version">
          v{item.versionNo}
        </span>
      </div>

      {/* Defaulted fields hint */}
      {dfCount > 0 && (
        <div className={`compare-defaulted-hint${dfCount >= 3 ? " compare-defaulted-warning" : ""}`}>
          {dfCount >= 3 ? `默认补全较多 ${dfCount} 项` : `默认补全 ${dfCount} 项`}
        </div>
      )}
      {dfCount === 0 && (
        <div className="compare-defaulted-hint">
          无默认补全
        </div>
      )}

      {/* Risk badge */}
      {item.metrics?.risk_level && (
        <div className="compare-risk-row">
          <RiskBadge level={item.metrics.risk_level} />
        </div>
      )}

      {/* Actions */}
      <div className="compare-item-actions">
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
  const labels: Record<string, string> = {
    low: "风险：低",
    medium: "风险：中",
    high: "风险：高",
    unknown: "风险：未知",
  };
  const riskLevel = level in labels ? level : "unknown";
  return (
    <span className={`compare-risk-badge risk-level risk-level-${riskLevel}`}>
      {labels[riskLevel]}
    </span>
  );
}

function SmallBtn({ label, onClick }: { label: string; onClick: () => void }): JSX.Element {
  return (
    <button
      className="toolbar-button compare-item-button"
      onClick={onClick}
    >
      {label}
    </button>
  );
}
