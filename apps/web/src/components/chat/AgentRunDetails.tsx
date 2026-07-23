"use client";

import { type JSX, useEffect, useState } from "react";
import type { WorkflowRuntimeStage } from "@/hooks/useWorkflowRuntime";
import { DefaultedFieldsNotice, type DefaultedField } from "@/components/runtime/DefaultedFieldsNotice";
import { FallbackToolNotice } from "@/components/chat/FallbackToolNotice";

export type AgentRunDetailsProps = {
  id?: string;
  jobId?: string;
  designId?: string;
  versionNo?: number;
  stages: WorkflowRuntimeStage[];
  artifacts: string[];
  errorMessage?: string;
  defaultedFields?: DefaultedField[];
  fallbackToolName?: string;
  fallbackConfidence?: number;
};

function formatDuration(ms: number | null): string {
  if (ms == null) return "-";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatTimestamp(ts: number | null): string {
  if (ts == null) return "-";
  return new Date(ts).toLocaleTimeString("zh-CN", { hour12: false });
}

export function AgentRunDetails({
  id,
  jobId,
  designId,
  versionNo,
  stages,
  artifacts,
  errorMessage,
  defaultedFields,
  fallbackToolName,
  fallbackConfidence,
}: AgentRunDetailsProps): JSX.Element {
  const STORAGE_KEY = "agent-run-details-open";
  const [isOpen, setIsOpen] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    try {
      return localStorage.getItem(STORAGE_KEY) === "true";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(isOpen));
    } catch {
      // ignore
    }
  }, [isOpen]);

  // Fully controlled <details>: the `open` prop is the single source of truth.
  // We toggle on <summary> click instead of the <details> onToggle event.
  // During generation the parent re-renders frequently; onToggle fires whenever
  // the DOM open state diverges from the prop (e.g. node remount), which created
  // a feedback loop flipping the panel open/closed repeatedly. Driving state from
  // the click handler breaks that loop while keeping user clicks working.
  return (
    <details id={id} className="agent-run-details" open={isOpen}>
      <summary
        onClick={(e) => {
          e.preventDefault();
          setIsOpen((prev) => !prev);
        }}
      >
        查看运行细节
      </summary>
      <div className="detail-grid">
        {jobId && (
          <div className="detail-row">
            <span className="detail-key">Job ID</span>
            <span className="detail-value">{jobId}</span>
          </div>
        )}
        {designId && (
          <div className="detail-row">
            <span className="detail-key">Design ID</span>
            <span className="detail-value">{designId}</span>
          </div>
        )}
        {versionNo != null && (
          <div className="detail-row">
            <span className="detail-key">Version</span>
            <span className="detail-value">{versionNo}</span>
          </div>
        )}

        {stages.length > 0 && (
          <>
            <div className="detail-row detail-section-title">
              <span className="detail-key">Stages</span>
            </div>
            {stages.map((s, i) => {
              const icon = s.status === "failed" ? "✗ " : s.status === "running" ? "⟳ " : "● ";
              const statusClass = s.status === "failed"
                ? " status-error"
                : s.status === "running"
                  ? " status-running"
                  : s.status === "completed"
                    ? " status-success"
                    : "";
              return (
                <div className={`detail-row workflow-stage-${s.status}${statusClass}`} key={i}>
                  <span className="detail-key">{icon}{s.label}</span>
                  <span className="detail-value">
                    {formatTimestamp(s.startedAt)}
                    {s.durationMs != null ? ` (${formatDuration(s.durationMs)})` : ""}
                  </span>
                </div>
              );
            })}
          </>
        )}

        {errorMessage && (
          <div className="detail-row detail-section-title status-error">
            <span className="detail-key">错误</span>
            <span className="detail-value">{errorMessage}</span>
          </div>
        )}

        {artifacts.length > 0 && (
          <>
            <div className="detail-row detail-section-title">
              <span className="detail-key">Artifacts</span>
            </div>
            {artifacts.map((a, i) => (
              <div className="detail-row" key={i}>
                <span className="detail-key" />
                <span className="detail-value">{a}</span>
              </div>
            ))}
          </>
        )}

        {defaultedFields && defaultedFields.length > 0 && (
          <DefaultedFieldsNotice fields={defaultedFields} />
        )}

        {fallbackToolName && fallbackConfidence != null && (
          <FallbackToolNotice toolName={fallbackToolName} confidence={fallbackConfidence} />
        )}
      </div>
    </details>
  );
}
