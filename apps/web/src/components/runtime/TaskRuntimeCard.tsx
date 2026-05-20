"use client";

import React, { type JSX } from "react";
import type { WorkflowRuntimeStage } from "../../hooks/useWorkflowRuntime";
import { getArtifactLabel } from "./taskRuntimeCardHtml";
import { UnifiedWorkflowTimeline } from "./UnifiedWorkflowTimeline";
import { WorkflowErrorCard } from "./WorkflowErrorCard";
import { getStageDescription } from "../chat/stageDescriptions";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

type TaskRuntimeCardProps = {
  label: string;
  isRunning: boolean;
  isFailed: boolean;
  stages: WorkflowRuntimeStage[];
  progress: number;
  elapsedTime: number;
  artifacts: string[];
  versionNo?: number;
  failedStageLabel?: string;
  errorMessage?: string;
  apiBaseUrl?: string;
  designId?: string;
  onRetry?: () => void;
  onViewDiagnostics?: () => void;
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TaskRuntimeCard(props: TaskRuntimeCardProps): JSX.Element {
  const {
    label,
    isRunning,
    isFailed,
    stages,
    progress,
    elapsedTime,
    artifacts,
    versionNo,
    failedStageLabel,
    errorMessage,
    apiBaseUrl,
    designId,
    onRetry,
    onViewDiagnostics,
  } = props;

  const isCompleted = !isRunning && !isFailed;

  // Header icon
  let headerIcon: JSX.Element;
  if (isRunning) {
    headerIcon = <span className="spinner" />;
  } else if (isFailed) {
    headerIcon = <span style={{ color: "#ef4444" }}>✗</span>;
  } else {
    headerIcon = <span style={{ color: "#10b981" }}>✓</span>;
  }

  // Card class modifier
  const cardClass = isRunning
    ? "tool-card tool-card-running"
    : isFailed
      ? "tool-card tool-card-failed"
      : "tool-card tool-card-done";

  return (
    <div className={cardClass}>
      {/* Header */}
      <div className="tool-card-header">
        {headerIcon}
        <span className="tool-card-name">{label}</span>
        {versionNo != null && (
          <span className="version-badge">v{versionNo}</span>
        )}
      </div>

      {/* Current stage description when running */}
      {isRunning && (() => {
        const runningStage = stages.find((s) => s.status === "running");
        if (!runningStage) return null;
        return (
          <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "8px", marginBottom: "4px" }}>
            {getStageDescription(runningStage.stage)}
          </div>
        );
      })()}

      {/* Timeline */}
      <div className="tool-card-body">
        <UnifiedWorkflowTimeline stages={stages} elapsedTime={elapsedTime} />

        {/* Progress bar when running */}
        {isRunning && progress > 0 && (
          <div className="workflow-progress-bar" style={{ marginTop: "8px" }}>
            <div
              style={{
                height: "4px",
                background: "var(--border-default)",
                borderRadius: "2px",
                overflow: "hidden",
              }}
            >
              <div
                className="workflow-progress-fill"
                style={{
                  height: "100%",
                  width: `${Math.min(progress, 100)}%`,
                  background: "var(--accent)",
                  borderRadius: "2px",
                  transition: "width 0.3s ease-out",
                }}
              />
            </div>
            <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
              {Math.round(progress)}%
            </div>
          </div>
        )}

        {/* Error card when failed */}
        {isFailed && (
          <WorkflowErrorCard
            failedStage={failedStageLabel ?? "未知阶段"}
            errorMessage={errorMessage ?? "生成失败"}
            onRetry={onRetry}
            onViewLogs={onViewDiagnostics}
          />
        )}

        {/* Artifact file list when completed */}
        {isCompleted && artifacts.length > 0 && (
          <div className="tool-card-artifacts">
            <div className="artifact-header">已生成 {artifacts.length} 个文件</div>
            <div className="artifact-list">
              {artifacts.map((key) => (
                <span key={key} className="artifact-badge">{getArtifactLabel(key)}</span>
              ))}
            </div>
          </div>
        )}

        {/* Download links for artifacts */}
        {isCompleted && artifacts.length > 0 && versionNo != null && apiBaseUrl && designId && (
          <div className="tool-card-files">
            {artifacts.map((f) => (
              <a
                key={f}
                className="tool-card-file"
                href={`${apiBaseUrl}/api/designs/${designId}/versions/${versionNo}/files/${encodeURIComponent(f)}`}
                target="_blank"
                rel="noreferrer"
              >
                {f}
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
