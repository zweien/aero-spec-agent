"use client";

import { type JSX } from "react";

export type AgentRunHeaderProps = {
  status: "idle" | "running" | "completed" | "failed";
  currentStageLabel?: string;
  progress: number;
  elapsedTime: number;
};

export function AgentRunHeader({
  status,
  currentStageLabel,
  progress,
  elapsedTime,
}: AgentRunHeaderProps): JSX.Element {
  if (status === "idle") return <></>;

  // Status icon
  let statusIcon: JSX.Element;
  if (status === "running") {
    statusIcon = <span className="status-icon" style={{ color: "var(--accent)" }}>&#10227;</span>;
  } else if (status === "completed") {
    statusIcon = <span className="status-icon" style={{ color: "var(--success)" }}>&#10003;</span>;
  } else {
    statusIcon = <span className="status-icon" style={{ color: "var(--error)" }}>&#10007;</span>;
  }

  // Title text
  let title: string;
  if (status === "running") {
    title = "正在设计飞机";
  } else if (status === "completed") {
    title = "设计完成";
  } else {
    title = "设计失败";
  }

  // Info line
  const elapsedSec = (elapsedTime / 1000).toFixed(1);
  const parts: string[] = [];
  if (currentStageLabel) parts.push(currentStageLabel);
  if (status === "running") parts.push(`${Math.round(progress)}%`);
  parts.push(`已运行 ${elapsedSec}s`);

  return (
    <div className="agent-run-header">
      {statusIcon}
      <span className="status-title">{title}</span>
      <span className="status-info">{parts.join(" · ")}</span>
    </div>
  );
}
