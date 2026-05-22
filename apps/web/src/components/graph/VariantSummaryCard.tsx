"use client";
import React, { type JSX, useEffect, useState } from "react";

import { VariantThumbnail } from "./VariantThumbnail";
import { AddToCompareButton } from "@/components/compare/AddToCompareButton";
import type { CompareItem } from "@/components/compare/types";

export type VariantSummaryCardProps = {
  label: string;
  status: string;
  versionNo: number;
  designId: string;
  apiBaseUrl: string;
  onLoadVersion: (designId: string, versionNo: number) => Promise<void>;
  onSwitchToParameters: () => void;
  isInCompare?: (id: string) => boolean;
  onAddToCompare?: (item: CompareItem) => void;
  compareFull?: boolean;
};

export function VariantSummaryCard({
  label,
  status,
  versionNo,
  designId,
  apiBaseUrl,
  onLoadVersion,
  onSwitchToParameters,
  isInCompare,
  onAddToCompare,
  compareFull,
}: VariantSummaryCardProps): JSX.Element {
  const [details, setDetails] = useState<{
    span?: number;
    rangeEst?: number;
    ldCruise?: number;
    aspectRatio?: number;
    wingLoading?: number;
  } | null>(null);
  const [trust, setTrust] = useState<{
    confidence_level?: string;
    generated_by?: string;
    defaulted_parameter_count?: number;
  } | null>(null);

  useEffect(() => {
    if (status !== "succeeded") return;
    let cancelled = false;
    fetch(`${apiBaseUrl}/api/designs/${designId}/versions/${versionNo}`)
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        const estimates =
          data?.validation_report?.performance_estimate?.estimates ?? [];
        const specEcho = data?.validation_report?.spec_echo;
        const findEst = (id: string) =>
          estimates.find((e: { estimate_id: string }) => e.estimate_id === id);
        setDetails({
          span: specEcho?.wing?.span?.value,
          rangeEst: findEst("range_est")?.value,
          ldCruise: findEst("ld_cruise")?.value,
          aspectRatio: findEst("aspect_ratio_perf")?.value,
          wingLoading: findEst("wing_loading_mtow")?.value,
        });
        const vt = data?.validation_report?.variant_trust;
        if (vt) setTrust(vt);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [status, designId, versionNo, apiBaseUrl]);

  const handleSetCurrent = async () => {
    await onLoadVersion(designId, versionNo);
    onSwitchToParameters();
  };

  const statusLabel =
    status === "succeeded"
      ? "✓ 已完成"
      : status === "failed"
        ? "✕ 失败"
        : status === "running"
          ? "⟳ 生成中"
          : status;

  return (
    <div className="variant-summary-card">
      {/* Header row */}
      <div className="variant-summary-header">
        <VariantThumbnail label={label} status={status as "succeeded" | "failed" | "running" | "queued"} />
        <div className="variant-summary-main">
          <div className="variant-summary-title-row">
            <span className="variant-summary-name">
              {label}
            </span>
            <span className={`variant-status variant-status-${status}`}>
              {statusLabel}
            </span>
          </div>
          <span className="variant-summary-version">
            v{versionNo}
            {trust && (
              <span
                className={`trust-badge trust-confidence-${trust.confidence_level ?? "unknown"}`}
              >
                {trust.confidence_level === "high" ? "高可信" : trust.confidence_level === "medium" ? "中可信" : "低可信"}
                {trust.generated_by === "fake_cad" ? " · Fake CAD" : ""}
              </span>
            )}
          </span>
        </div>
      </div>

      {/* Metrics grid */}
      {details && (
        <div className="variant-summary-metrics">
          <MetricItem label="翼展" value={details.span} unit="m" />
          <MetricItem label="航程" value={details.rangeEst} unit="km" prefix="~" />
          <MetricItem label="L/D" value={details.ldCruise} />
          <MetricItem label="展弦比" value={details.aspectRatio} />
          <MetricItem label="翼载" value={details.wingLoading} unit="kg/m²" />
        </div>
      )}

      {/* Action buttons */}
      <div className="graph-card-actions">
        <SmallButton
          label="查看模型"
          onClick={async () => {
            await onLoadVersion(designId, versionNo);
          }}
          disabled={status !== "succeeded"}
        />
        <SmallButton
          label="设为当前方案"
          onClick={handleSetCurrent}
          disabled={status !== "succeeded"}
        />
        {onAddToCompare && (
          <AddToCompareButton
            isAdded={!!isInCompare?.(`${designId}-v${versionNo}`)}
            maxReached={compareFull && !isInCompare?.(`${designId}-v${versionNo}`)}
            onAdd={() => onAddToCompare({
              id: `${designId}-v${versionNo}`,
              designId,
              versionNo,
              name: label,
              source: "deep-design-variant",
            })}
            disabled={status !== "succeeded"}
          />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function MetricItem({
  label,
  value,
  unit,
  prefix,
}: {
  label: string;
  value?: number;
  unit?: string;
  prefix?: string;
}): JSX.Element | null {
  if (value == null) return null;
  const display = `${prefix ?? ""}${typeof value === "number" ? value.toFixed(1) : value}${unit ?? ""}`;
  return (
    <div className="variant-metric-item">
      <span className="variant-metric-label">{label}:</span>
      <span className="variant-metric-value">
        {display}
      </span>
    </div>
  );
}

function SmallButton({
  label,
  onClick,
  disabled,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}): JSX.Element {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="toolbar-button graph-card-button"
    >
      {label}
    </button>
  );
}
