"use client";

import React, { type JSX } from "react";

import { getStepLabel, type WorkflowStage } from "./useJobEventStream";

export type WorkflowTimelineProps = {
  stages: WorkflowStage[];
};

type StepState = "completed" | "running" | "failed" | "pending";

const STATE_COLORS: Record<StepState, string> = {
  completed: "var(--success)",
  running: "var(--accent)",
  failed: "var(--error)",
  pending: "var(--text-muted)",
};

const ALL_STEPS = [
  "writing_spec",
  "geometry_building",
  "mesh_export",
  "report_generating",
  "generating_cad",
];

function circleIcon(state: StepState): string {
  switch (state) {
    case "completed":
      return "●";
    case "running":
      return "◉";
    case "failed":
      return "✗";
    default:
      return "○";
  }
}

function inferStepStates(stages: WorkflowStage[]): Array<{ step: string; state: StepState }> {
  // Find the highest pipeline step index we've seen — all steps before it are completed
  let highWaterMark = -1;
  let hasSucceeded = false;

  for (const s of stages) {
    if (s.step === "succeeded") {
      hasSucceeded = true;
      continue;
    }
    const idx = ALL_STEPS.indexOf(s.step);
    if (idx >= 0 && idx > highWaterMark) {
      highWaterMark = idx;
    }
  }

  const result: Array<{ step: string; state: StepState }> = [];
  for (let i = 0; i < ALL_STEPS.length; i++) {
    let state: StepState;
    if (hasSucceeded || i < highWaterMark) {
      state = "completed";
    } else if (i === highWaterMark) {
      state = "running";
    } else {
      state = "pending";
    }
    result.push({ step: ALL_STEPS[i], state });
  }

  return result;
}

export function WorkflowTimeline({ stages }: WorkflowTimelineProps): JSX.Element {
  if (stages.length === 0) return <div />;

  const steps = inferStepStates(stages);

  return (
    <div style={{ display: "flex", flexDirection: "column", marginTop: "8px" }}>
      {steps.map((item, i) => {
        const isLast = i === steps.length - 1;
        const isRunning = item.state === "running";
        const color = STATE_COLORS[item.state];

        return (
          <div key={item.step}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span
                style={{
                  color,
                  fontSize: "16px",
                  lineHeight: 1,
                  animation: isRunning ? "pulse 1.5s ease-in-out infinite" : "none",
                }}
              >
                {circleIcon(item.state)}
              </span>
              <span
                style={{
                  fontSize: "13px",
                  color: item.state === "pending" ? "var(--text-muted)" : "var(--text)",
                }}
              >
                {getStepLabel(item.step)}
              </span>
            </div>

            {!isLast && (
              <div
                style={{
                  marginLeft: "7px",
                  borderLeft: "2px solid var(--border-default)",
                  height: "16px",
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
