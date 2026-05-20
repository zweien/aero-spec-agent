"use client";
import React, { type JSX, useCallback, useState } from "react";
import { AddToCompareButton } from "@/components/compare/AddToCompareButton";
import type { CompareItem } from "@/components/compare/types";

export type RecommendedVariantCardProps = {
  report: string;
  variants: Array<{ label: string; status: string; versionNo: number }>;
  designId: string;
  apiBaseUrl: string;
  onLoadVersion: (designId: string, versionNo: number) => Promise<void>;
  onSwitchToParameters: () => void;
  isInCompare?: (id: string) => boolean;
  onAddToCompare?: (item: CompareItem) => void;
};

export function RecommendedVariantCard({
  report,
  variants,
  designId,
  apiBaseUrl,
  onLoadVersion,
  onSwitchToParameters,
  isInCompare,
  onAddToCompare,
}: RecommendedVariantCardProps): JSX.Element {
  const [applying, setApplying] = useState(false);

  const { recommended, reason, reasons } = parseRecommendation(report, variants);

  const handleApply = useCallback(async () => {
    if (!recommended) return;
    setApplying(true);
    try {
      await onLoadVersion(designId, recommended.versionNo);
      onSwitchToParameters();
    } finally {
      setApplying(false);
    }
  }, [recommended, designId, onLoadVersion, onSwitchToParameters]);

  const handleView = useCallback(async () => {
    if (!recommended) return;
    await onLoadVersion(designId, recommended.versionNo);
  }, [recommended, designId, onLoadVersion]);

  if (!recommended) return <></>;

  return (
    <div
      style={{
        background: "var(--accent-bg)",
        border: "1px solid var(--accent-border)",
        borderRadius: "var(--radius)",
        padding: 12,
        boxShadow: "0 0 12px rgba(100,120,255,0.15), 0 0 4px rgba(100,120,255,0.1)",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 6,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: "var(--accent-bright)",
            }}
          >
            推荐方案: {recommended.label}
          </span>
          <span
            style={{
              fontSize: 9,
              fontWeight: 700,
              color: "#fff",
              background: "var(--accent)",
              borderRadius: 3,
              padding: "1px 5px",
              letterSpacing: "0.5px",
              textTransform: "uppercase",
            }}
          >
            AI 推荐
          </span>
        </div>
        <span
          style={{
            fontSize: 10,
            color: "var(--accent)",
            background: "var(--accent-bg)",
            border: "1px solid var(--accent-border)",
            borderRadius: "var(--radius-sm)",
            padding: "1px 6px",
          }}
        >
          v{recommended.versionNo}
        </span>
      </div>

      {/* Structured reasons */}
      {reasons.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text)", display: "block", marginBottom: 3 }}>
            推荐原因：
          </span>
          {reasons.map((r, i) => (
            <div key={i} style={{ display: "flex", gap: 4, alignItems: "baseline", marginBottom: 1 }}>
              <span style={{ fontSize: 11, color: "var(--success)" }}>✓</span>
              <span style={{ fontSize: 11, color: "var(--text-dim)" }}>{r}</span>
            </div>
          ))}
        </div>
      )}

      {/* Fallback single-line reason if no structured reasons */}
      {reasons.length === 0 && reason && (
        <p
          style={{
            fontSize: 12,
            color: "var(--text-dim)",
            margin: "0 0 8px 0",
            lineHeight: 1.5,
          }}
        >
          {reason}
        </p>
      )}

      {/* Actions */}
      <div style={{ display: "flex", gap: 6 }}>
        <button
          onClick={handleView}
          style={{
            fontSize: 11,
            padding: "4px 8px",
            background: "transparent",
            border: "1px solid var(--accent-border)",
            borderRadius: "var(--radius-sm)",
            color: "var(--accent)",
            cursor: "pointer",
          }}
        >
          查看模型
        </button>
        <button
          onClick={handleApply}
          disabled={applying}
          style={{
            fontSize: 11,
            padding: "4px 10px",
            background: "var(--accent)",
            border: "none",
            borderRadius: "var(--radius-sm)",
            color: "#fff",
            cursor: applying ? "wait" : "pointer",
            opacity: applying ? 0.7 : 1,
            fontWeight: 500,
          }}
        >
          {applying ? "应用中..." : "应用此方案"}
        </button>
        {onAddToCompare && recommended && (
          <AddToCompareButton
            isAdded={!!isInCompare?.(`${designId}-v${recommended.versionNo}`)}
            onAdd={() => onAddToCompare({
              id: `${designId}-v${recommended.versionNo}`,
              designId,
              versionNo: recommended.versionNo,
              name: recommended.label,
              source: "recommended",
            })}
          />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseRecommendation(
  report: string,
  variants: Array<{ label: string; status: string; versionNo: number }>,
): {
  recommended: { label: string; status: string; versionNo: number } | null;
  reason: string | null;
  reasons: string[];
} {
  const empty = { recommended: null, reason: null, reasons: [] as string[] };
  if (!report || variants.length === 0) return empty;

  // Try to find explicit recommendation markers in the report
  const patterns = [
    /推荐[：:]\s*\*{0,2}([^*\n,，]+)/,
    /Recommendation[：:]\s*\*{0,2}([^*\n,，]+)/i,
    /推荐方案[是为]?\s*\*{0,2}([^*\n,，]+)/,
    /best\s+(?:choice|option|variant)[：:]\s*\*{0,2}([^*\n,，]+)/i,
  ];

  for (const pattern of patterns) {
    const match = report.match(pattern);
    if (match) {
      const rawLabel = match[1].trim().replace(/\*+$/, "").trim();
      const matched =
        variants.find((v) => v.label === rawLabel) ??
        variants.find((v) => rawLabel.includes(v.label)) ??
        variants.find((v) => v.label.includes(rawLabel));
      if (matched) {
        const afterMatch = report.slice((match.index ?? 0) + match[0].length);
        const reasonLine = afterMatch
          .split(/[\n。]/)[0]
          .trim()
          .replace(/^[—\-–]\s*/, "");

        // Extract structured reasons from report (lines starting with ✓ or -)
        const structuredReasons = extractStructuredReasons(report, matched.label);

        return {
          recommended: matched,
          reason: reasonLine || null,
          reasons: structuredReasons,
        };
      }
    }
  }

  const fallback = variants.find((v) => v.status === "succeeded") ?? null;
  return {
    recommended: fallback,
    reason: fallback ? "首个成功生成的方案" : null,
    reasons: fallback ? ["首个成功生成的方案"] : [],
  };
}

function extractStructuredReasons(report: string, label: string): string[] {
  const reasons: string[] = [];

  // Look for lines with performance improvements or key advantages near the label
  const lines = report.split("\n");
  const labelIdx = lines.findIndex((l) => l.includes(label));

  // Search in a window around the label mention and after "推荐"
  const searchStart = Math.max(0, labelIdx - 3);
  const searchEnd = Math.min(lines.length, labelIdx + 15);

  for (let i = searchStart; i < searchEnd; i++) {
    const line = lines[i].trim();
    // Match lines with ✓, -, or key metrics
    if (/^[✓✔]/.test(line)) {
      reasons.push(line.replace(/^[✓✔]\s*/, ""));
    } else if (/^[-•]\s/.test(line) && /(?:升阻比|航程|翼载|展弦比|优化|最佳|提升|降低|改善|稳定)/.test(line)) {
      reasons.push(line.replace(/^[-•]\s*/, ""));
    }
    if (reasons.length >= 3) break;
  }

  return reasons;
}
