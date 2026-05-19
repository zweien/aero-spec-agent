"use client";
import React, { type JSX, useEffect, useState } from "react";

import { VariantThumbnail } from "./VariantThumbnail";

export type VariantSummaryCardProps = {
  label: string;
  status: string;
  versionNo: number;
  designId: string;
  apiBaseUrl: string;
  onLoadVersion: (designId: string, versionNo: number) => Promise<void>;
  onSwitchToParameters: () => void;
};

export function VariantSummaryCard({
  label,
  status,
  versionNo,
  designId,
  apiBaseUrl,
  onLoadVersion,
  onSwitchToParameters,
}: VariantSummaryCardProps): JSX.Element {
  const [details, setDetails] = useState<{
    span?: number;
    rangeEst?: number;
    ldCruise?: number;
    aspectRatio?: number;
    wingLoading?: number;
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

  const statusColor =
    status === "succeeded"
      ? "var(--success)"
      : status === "failed"
        ? "var(--error)"
        : "var(--text-muted)";

  const statusLabel =
    status === "succeeded"
      ? "succeeded"
      : status === "failed"
        ? "failed"
        : status === "running"
          ? "running"
          : status;

  return (
    <div
      style={{
        background: "var(--bg-elevated)",
        border: "1px solid var(--border-default)",
        borderRadius: "var(--radius)",
        padding: 12,
      }}
    >
      {/* Header row */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 8,
        }}
      >
        <VariantThumbnail label={label} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 6,
            }}
          >
            <span
              style={{
                fontSize: 13,
                fontWeight: 600,
                color: "var(--text)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {label}
            </span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 600,
                color: statusColor,
                background:
                  status === "succeeded"
                    ? "var(--success-bg)"
                    : status === "failed"
                      ? "var(--error-bg)"
                      : "var(--bg-surface)",
                border:
                  status === "succeeded"
                    ? "1px solid var(--success-border)"
                    : status === "failed"
                      ? "1px solid var(--error)"
                      : "1px solid var(--border-default)",
                borderRadius: "var(--radius-sm)",
                padding: "1px 6px",
                flexShrink: 0,
              }}
            >
              {statusLabel}
            </span>
          </div>
          <span
            style={{
              fontSize: 11,
              color: "var(--text-dim)",
            }}
          >
            v{versionNo}
          </span>
        </div>
      </div>

      {/* Metrics grid */}
      {details && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "2px 12px",
            marginBottom: 8,
          }}
        >
          <MetricItem label="翼展" value={details.span} unit="m" />
          <MetricItem label="航程" value={details.rangeEst} unit="km" prefix="~" />
          <MetricItem label="L/D" value={details.ldCruise} />
          <MetricItem label="展弦比" value={details.aspectRatio} />
          <MetricItem label="翼载" value={details.wingLoading} unit="kg/m²" />
        </div>
      )}

      {/* Action buttons */}
      <div style={{ display: "flex", gap: 6 }}>
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
    <div style={{ display: "flex", gap: 4, alignItems: "baseline" }}>
      <span style={{ fontSize: 11, color: "var(--text-dim)" }}>{label}:</span>
      <span style={{ fontSize: 12, color: "var(--text)", fontWeight: 500 }}>
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
      style={{
        fontSize: 11,
        padding: "4px 8px",
        background: "transparent",
        border: "1px solid var(--border-default)",
        borderRadius: "var(--radius-sm)",
        color: disabled ? "var(--text-muted)" : "var(--text-dim)",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {label}
    </button>
  );
}
