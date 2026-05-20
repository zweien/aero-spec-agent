"use client";

import { type JSX, useEffect, useRef, useState } from "react";
import type { WorkflowRuntimeStage } from "@/hooks/useWorkflowRuntime";
import { DefaultedFieldsNotice, type DefaultedField } from "@/components/runtime/DefaultedFieldsNotice";

export type AgentRunDetailsProps = {
  id?: string;
  jobId?: string;
  designId?: string;
  versionNo?: number;
  stages: WorkflowRuntimeStage[];
  artifacts: string[];
  errorMessage?: string;
  defaultedFields?: DefaultedField[];
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
  const detailsRef = useRef<HTMLDetailsElement>(null);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(isOpen));
    } catch {
      // ignore
    }
  }, [isOpen]);

  // Sync the <details> open state with React state
  useEffect(() => {
    if (detailsRef.current) {
      detailsRef.current.open = isOpen;
    }
  }, [isOpen]);

  const handleToggle = () => {
    setIsOpen((prev) => !prev);
  };

  return (
    <details id={id} className="agent-run-details" ref={detailsRef} onToggle={handleToggle}>
      <summary>查看运行细节</summary>
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
            <div className="detail-row" style={{ marginTop: 6 }}>
              <span className="detail-key" style={{ fontWeight: 600 }}>Stages</span>
            </div>
            {stages.map((s, i) => {
              const icon = s.status === "failed" ? "✗ " : s.status === "running" ? "⟳ " : "● ";
              const rowStyle = s.status === "failed" ? { color: "var(--error, #e53e3e)" } : undefined;
              return (
                <div className="detail-row" key={i} style={rowStyle}>
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
          <div className="detail-row" style={{ marginTop: 6 }}>
            <span className="detail-key" style={{ fontWeight: 600, color: "var(--error, #e53e3e)" }}>错误</span>
            <span className="detail-value" style={{ color: "var(--error, #e53e3e)" }}>{errorMessage}</span>
          </div>
        )}

        {artifacts.length > 0 && (
          <>
            <div className="detail-row" style={{ marginTop: 6 }}>
              <span className="detail-key" style={{ fontWeight: 600 }}>Artifacts</span>
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
      </div>
    </details>
  );
}
