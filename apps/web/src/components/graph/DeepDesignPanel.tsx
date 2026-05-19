"use client";

import React, { type JSX, useEffect, useState } from "react";

import type { useDeepDesignStream } from "./useDeepDesignStream";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export type DeepDesignPanelProps = {
  apiBaseUrl: string;
  defaultSpec?: Record<string, unknown>;
  stream: ReturnType<typeof useDeepDesignStream>;
  onComplete?: () => void;
  onStart?: () => void;
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DeepDesignPanel({
  apiBaseUrl,
  defaultSpec,
  stream,
  onComplete,
  onStart,
}: DeepDesignPanelProps): JSX.Element {
  const [description, setDescription] = useState("");
  const [variantCount, setVariantCount] = useState(3);
  const [specJson, setSpecJson] = useState(
    defaultSpec ? JSON.stringify(defaultSpec, null, 2) : "",
  );

  // Sync defaultSpec changes into textarea
  useEffect(() => {
    if (defaultSpec) {
      setSpecJson(JSON.stringify(defaultSpec, null, 2));
    }
  }, [defaultSpec]);

  // Fire onComplete when stream transitions to completed
  const prevStatusRef = React.useRef(stream.status);
  useEffect(() => {
    if (prevStatusRef.current === "running" && stream.status === "completed") {
      onComplete?.();
    }
    prevStatusRef.current = stream.status;
  }, [stream.status, onComplete]);

  const handleSubmit = () => {
    if (!description.trim()) return;

    let baseSpec: Record<string, unknown> = {};
    try {
      baseSpec = specJson.trim() ? JSON.parse(specJson) : {};
    } catch {
      baseSpec = {};
    }

    onStart?.();
    void stream.start(apiBaseUrl, {
      design_id: `dd-${Date.now()}`,
      description: description.trim(),
      base_spec: baseSpec,
      constraints: { variant_count: variantCount },
    });
  };

  const isRunning = stream.status === "running";
  const hasNoSpec = !defaultSpec && !specJson.trim();

  return (
    <div className="flex flex-col gap-3">
      {/* No spec notice */}
      {hasNoSpec && (
        <div style={{
          padding: "12px",
          background: "var(--warning-bg)",
          border: "1px solid var(--warning)",
          borderRadius: "var(--radius-sm)",
          color: "var(--warning)",
          fontSize: "12px",
        }}>
          请先通过对话生成或加载一个基础设计，或手动输入 JSON。
        </div>
      )}

      {/* Input form */}
      <div style={{
        padding: "12px",
        background: "var(--bg-elevated)",
        borderRadius: "var(--radius)",
        border: "1px solid var(--border-default)",
      }}>
        <div style={{ marginBottom: "10px" }}>
          <label style={{ display: "block", fontSize: "12px", fontWeight: 500, color: "var(--text-dim)", marginBottom: "4px" }}>
            设计需求描述
          </label>
          <textarea
            style={{
              width: "100%",
              padding: "8px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border-strong)",
              background: "var(--bg-base)",
              color: "var(--text)",
              fontSize: "13px",
              resize: "vertical",
            }}
            rows={2}
            placeholder="e.g. 设计一架 300km 航程的长航时无人机"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={isRunning}
          />
        </div>

        <div style={{ display: "flex", gap: "12px", marginBottom: "10px" }}>
          <div style={{ flex: 1 }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 500, color: "var(--text-dim)", marginBottom: "4px" }}>
              变体数量
            </label>
            <input
              type="number"
              style={{
                width: "100%",
                padding: "8px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-strong)",
                background: "var(--bg-base)",
                color: "var(--text)",
                fontSize: "13px",
              }}
              min={1}
              max={5}
              value={variantCount}
              onChange={(e) => setVariantCount(Number(e.target.value) || 3)}
              disabled={isRunning}
            />
          </div>
        </div>

        <div style={{ marginBottom: "10px" }}>
          <label style={{ display: "block", fontSize: "12px", fontWeight: 500, color: "var(--text-dim)", marginBottom: "4px" }}>
            Base Spec (JSON)
          </label>
          <textarea
            style={{
              width: "100%",
              padding: "8px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border-strong)",
              background: "var(--bg-base)",
              color: "var(--text)",
              fontFamily: "var(--font-mono)",
              fontSize: "11px",
              resize: "vertical",
            }}
            rows={4}
            placeholder="{}"
            value={specJson}
            onChange={(e) => setSpecJson(e.target.value)}
            disabled={isRunning}
          />
        </div>

        <div style={{ display: "flex", gap: "8px" }}>
          <button
            onClick={handleSubmit}
            disabled={isRunning || !description.trim()}
          >
            {isRunning ? "运行中..." : "开始探索"}
          </button>
          {isRunning && (
            <button
              style={{ background: "var(--bg-surface)", color: "var(--text-dim)" }}
              onClick={stream.stop}
            >
              取消
            </button>
          )}
        </div>
      </div>

      {/* Report */}
      {stream.report && (
        <div style={{
          padding: "12px",
          background: "var(--bg-elevated)",
          borderRadius: "var(--radius)",
          border: "1px solid var(--border-default)",
        }}>
          <h4 style={{ fontSize: "12px", fontWeight: 600, color: "var(--text)", marginBottom: "8px" }}>
            设计探索报告
          </h4>
          <pre style={{
            whiteSpace: "pre-wrap",
            fontSize: "11px",
            color: "var(--text-dim)",
            margin: 0,
            lineHeight: 1.6,
          }}>
            {stream.report}
          </pre>
        </div>
      )}
    </div>
  );
}
