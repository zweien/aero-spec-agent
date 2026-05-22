"use client";

import React, { type JSX, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { UnifiedWorkflowTimeline } from "../runtime/UnifiedWorkflowTimeline";
import { RecommendedVariantCard } from "./RecommendedVariantCard";
import { VariantSummaryCard } from "./VariantSummaryCard";
import type { useDeepDesignStream } from "./useDeepDesignStream";
import type { CompareItem } from "@/components/compare/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export type DeepDesignPanelProps = {
  apiBaseUrl: string;
  defaultSpec?: Record<string, unknown>;
  stream: ReturnType<typeof useDeepDesignStream>;
  onComplete?: () => void;
  onStart?: () => void;
  designId: string | null;
  onLoadVersion: (designId: string, versionNo: number) => Promise<void>;
  onSwitchToParameters: () => void;
  isInCompare?: (id: string) => boolean;
  onAddToCompare?: (item: CompareItem) => void;
  compareFull?: boolean;
};

// ---------------------------------------------------------------------------
// Exploration depth config
// ---------------------------------------------------------------------------

const DEPTH_MAP: Record<string, number> = { quick: 2, standard: 3, deep: 5 };

const strategyLabels: Record<string, string> = {
  endurance: "长航时优化",
  speed: "高速优化",
  payload: "载荷优化",
  stol: "短距起降",
};

const STRATEGY_OPTIONS = [
  { key: "endurance", label: strategyLabels.endurance },
  { key: "speed", label: strategyLabels.speed },
  { key: "payload", label: strategyLabels.payload },
  { key: "stol", label: strategyLabels.stol },
] as const;

// ---------------------------------------------------------------------------
// Stage label helper
// ---------------------------------------------------------------------------

function getCurrentStageLabel(nodes: { name: string; label: string; state: string }[]): string | null {
  for (let i = nodes.length - 1; i >= 0; i--) {
    if (nodes[i].state === "running") return nodes[i].label;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DeepDesignPanel({
  apiBaseUrl,
  defaultSpec,
  stream,
  onComplete,
  onStart,
  designId,
  onLoadVersion,
  onSwitchToParameters,
  isInCompare,
  onAddToCompare,
  compareFull,
}: DeepDesignPanelProps): JSX.Element {
  const [description, setDescription] = useState("");
  const [explorationDepth, setExplorationDepth] = useState<"quick" | "standard" | "deep">("standard");
  const [strategies, setStrategies] = useState<Set<string>>(new Set());
  const [specJson, setSpecJson] = useState(
    defaultSpec ? JSON.stringify(defaultSpec, null, 2) : "",
  );
  const [showRuntimeDetails, setShowRuntimeDetails] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("dd-show-runtime-details") === "true";
  });
  const [showAdvanced, setShowAdvanced] = useState(false);

  const toggleRuntimeDetails = () => {
    setShowRuntimeDetails((prev) => {
      const next = !prev;
      try { localStorage.setItem("dd-show-runtime-details", String(next)); } catch {}
      return next;
    });
  };

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

  // ---- Submit ----
  const handleSubmit = () => {
    if (!description.trim()) return;

    const variantCount = DEPTH_MAP[explorationDepth];

    let baseSpec: Record<string, unknown> = {};
    try {
      baseSpec = specJson.trim() ? JSON.parse(specJson) : {};
    } catch {
      baseSpec = {};
    }

    const strategyParts = Array.from(strategies)
      .map((s) => strategyLabels[s])
      .filter(Boolean);
    let fullDescription = description.trim();
    if (strategyParts.length > 0) {
      fullDescription += `。重点考虑：${strategyParts.join("、")}`;
    }

    onStart?.();
    void stream.start(apiBaseUrl, {
      design_id: designId ?? `dd-${Date.now()}`,
      description: fullDescription,
      base_spec: baseSpec,
      constraints: { variant_count: variantCount },
    });
  };

  // ---- Export ----
  const handleExport = () => {
    const blob = new Blob([stream.report], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const id = designId ?? "unknown";
    const count = stream.variants.length;
    const date = new Date().toISOString().slice(0, 10);
    a.download = `deep-design-${id}-${count}variants-${date}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // ---- Strategy toggle ----
  const toggleStrategy = (key: string) => {
    setStrategies((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  // ---- Derived state ----
  const isRunning = stream.status === "running";
  const hasNoSpec = !defaultSpec && !specJson.trim();
  const succeededVariants = stream.variants.filter((v) => v.status === "succeeded");
  const currentStageLabel = getCurrentStageLabel(stream.nodes);
  const runningVariantCount = stream.variants.filter((v) => v.status === "succeeded").length;
  const variantDesignId = stream.ddDesignId ?? designId;

  return (
    <div className="deep-design-panel">
      {/* ---- Idle: no spec notice ---- */}
      {hasNoSpec && (
        <div className="deep-design-section notice notice-info deep-design-empty-notice">
          <div className="deep-design-notice-title">
            请先生成或加载一个基础设计，再进行深度设计探索。
          </div>
          <div className="deep-design-note">
            提示：在左侧对话框中描述你的设计需求，AI 将为你生成初始方案。或手动输入 JSON 规格。
          </div>
        </div>
      )}

      {/* ---- Input form ---- */}
      <div className="deep-design-section deep-design-form">
        {/* Description */}
        <div className="deep-design-field">
          <label className="field-label">设计需求描述</label>
          <textarea
            className="deep-design-prompt"
            rows={2}
            placeholder="e.g. 设计一架 300km 航程的长航时无人机"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={isRunning}
          />
        </div>

        {/* Strategy checkboxes (2x2 grid) */}
        <div className="deep-design-field">
          <label className="field-label">优化策略</label>
          <div className="deep-design-strategies">
            {STRATEGY_OPTIONS.map((opt) => (
              <label
                key={opt.key}
                className="deep-design-choice deep-design-strategy"
              >
                <input
                  type="checkbox"
                  checked={strategies.has(opt.key)}
                  onChange={() => toggleStrategy(opt.key)}
                  disabled={isRunning}
                />
                {opt.label}
              </label>
            ))}
          </div>
        </div>

        {/* Exploration depth radio buttons */}
        <div className="deep-design-field">
          <label className="field-label">探索深度</label>
          <div className="deep-design-depth-controls">
            {(["quick", "standard", "deep"] as const).map((depth) => {
              const labels: Record<string, string> = {
                quick: `快速探索 (${DEPTH_MAP.quick})`,
                standard: `标准探索 (${DEPTH_MAP.standard})`,
                deep: `深度探索 (${DEPTH_MAP.deep})`,
              };
              return (
                <label
                  key={depth}
                  className="deep-design-choice deep-design-depth"
                >
                  <input
                    type="radio"
                    name="explorationDepth"
                    checked={explorationDepth === depth}
                    onChange={() => setExplorationDepth(depth)}
                    disabled={isRunning}
                  />
                  {labels[depth]}
                </label>
              );
            })}
          </div>
        </div>

        {/* Advanced: Base Spec JSON (collapsible) */}
        <div className="deep-design-field">
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="toolbar-button deep-design-disclosure"
          >
            {showAdvanced ? "▼ 高级选项" : "▶ 高级选项"}
          </button>
          {showAdvanced && (
            <div className="deep-design-advanced">
              <label className="field-label">Base Spec (JSON)</label>
              <textarea
                className="deep-design-prompt deep-design-spec-input"
                rows={4}
                placeholder="{}"
                value={specJson}
                onChange={(e) => setSpecJson(e.target.value)}
                disabled={isRunning}
              />
            </div>
          )}
        </div>

        {/* Submit / Cancel */}
        <div className="deep-design-actions">
          <button
            onClick={handleSubmit}
            disabled={isRunning || !description.trim()}
            className="button-primary"
          >
            {isRunning ? "运行中..." : "开始探索"}
          </button>
          {isRunning && (
            <button
              className="deep-design-cancel"
              onClick={stream.stop}
            >
              取消
            </button>
          )}
        </div>
      </div>

      {/* ---- Running: status bar ---- */}
      {isRunning && (
        <>
          <div className="deep-design-section deep-design-status">
            <div className="deep-design-status-title">
              AI 正在探索设计方案...
            </div>
            <div className="deep-design-status-meta">
              {currentStageLabel && `当前阶段：${currentStageLabel}`}
              {runningVariantCount > 0 && ` · 已完成 ${runningVariantCount} 个方案`}
            </div>
          </div>

          {/* Timeline */}
          <UnifiedWorkflowTimeline nodes={stream.nodes} mode="deep-design" />

          {/* Collapsible runtime details */}
          <div className="deep-design-runtime">
            <button
              onClick={toggleRuntimeDetails}
              className="toolbar-button deep-design-disclosure"
            >
              {showRuntimeDetails ? "▼ 隐藏运行细节" : "▶ 查看运行细节"}
            </button>
            {showRuntimeDetails && (
              <div className="deep-design-runtime-log">
                {stream.events.map((e, i) => (
                  <div key={i}>
                    [{e.timestamp}] {e.eventType} {e.detail ?? ""}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* ---- Completed: results ---- */}
      {stream.status === "completed" && (
        <>
          {/* Recommended variant */}
          {succeededVariants.length > 0 && variantDesignId && (
            <RecommendedVariantCard
              report={stream.report}
              variants={succeededVariants.map((v) => ({
                label: v.label,
                status: v.status,
                versionNo: v.versionNo ?? 0,
              }))}
              designId={variantDesignId}
              apiBaseUrl={apiBaseUrl}
              onLoadVersion={onLoadVersion}
              onSwitchToParameters={onSwitchToParameters}
              isInCompare={isInCompare}
              onAddToCompare={onAddToCompare}
              compareFull={compareFull}
            />
          )}

          {/* Variant cards */}
          {stream.variants.map((v) => (
            <VariantSummaryCard
              key={v.jobId ?? v.label}
              label={v.label}
              status={v.status}
              versionNo={v.versionNo ?? 0}
              designId={variantDesignId ?? ""}
              apiBaseUrl={apiBaseUrl}
              onLoadVersion={onLoadVersion}
              onSwitchToParameters={onSwitchToParameters}
              isInCompare={isInCompare}
              onAddToCompare={onAddToCompare}
              compareFull={compareFull}
            />
          ))}

          {/* Report with markdown */}
          {stream.report && (
            <div className="deep-design-section deep-design-report">
              <div className="deep-design-report-header">
                <h4 className="deep-design-heading">
                  设计探索报告
                </h4>
                <button
                  onClick={handleExport}
                  className="toolbar-button"
                >
                  导出 .md
                </button>
              </div>
              <div className="deep-design-report-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {stream.report}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {/* Next steps suggestion */}
          <div className="deep-design-section deep-design-next-steps">
            <h4 className="deep-design-heading">
              下一步建议
            </h4>
            <ul className="deep-design-suggestions">
              <li>选择推荐方案后，在参数面板中进一步优化翼载和发动机参数</li>
              <li>使用 VSPAERO 分析工具验证气动性能</li>
              <li>尝试不同尾翼布局（T-tail / V-tail）的方案对比</li>
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
