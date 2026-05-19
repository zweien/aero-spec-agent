"use client";
import React, { type JSX, useCallback, useState } from "react";

export type RecommendedVariantCardProps = {
  report: string;
  variants: Array<{ label: string; status: string; versionNo: number }>;
  designId: string;
  apiBaseUrl: string;
  onLoadVersion: (designId: string, versionNo: number) => Promise<void>;
  onSwitchToParameters: () => void;
};

export function RecommendedVariantCard({
  report,
  variants,
  designId,
  apiBaseUrl,
  onLoadVersion,
  onSwitchToParameters,
}: RecommendedVariantCardProps): JSX.Element {
  const [applying, setApplying] = useState(false);

  const { recommended, reason } = parseRecommendation(report, variants);

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

  if (!recommended) return <></>;

  return (
    <div
      style={{
        background: "var(--accent-bg)",
        border: "1px solid var(--accent-border)",
        borderRadius: "var(--radius)",
        padding: 12,
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

      {/* Reason */}
      {reason && (
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

      {/* Action */}
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
} {
  if (!report || variants.length === 0) {
    return { recommended: null, reason: null };
  }

  // Try to find explicit recommendation markers in the report
  // Patterns: "推荐：<label>" or "Recommendation: <label>"
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
      // Find matching variant — allow partial match
      const matched =
        variants.find((v) => v.label === rawLabel) ??
        variants.find((v) => rawLabel.includes(v.label)) ??
        variants.find((v) => v.label.includes(rawLabel));
      if (matched) {
        // Extract the sentence or line after the match as the reason
        const afterMatch = report.slice((match.index ?? 0) + match[0].length);
        const reasonLine = afterMatch
          .split(/[\n。]/)[0]
          .trim()
          .replace(/^[—\-–]\s*/, "");
        return { recommended: matched, reason: reasonLine || null };
      }
    }
  }

  // Fallback: first succeeded variant
  const fallback = variants.find((v) => v.status === "succeeded") ?? null;
  return { recommended: fallback, reason: fallback ? "首个成功生成的方案" : null };
}
