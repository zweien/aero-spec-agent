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
  const result: Array<{ step: string; state: StepState }> = [];
  const seen = new Map<string, StepState>();

  for (const s of stages) {
    if (s.step === "succeeded") {
      seen.set("generating_cad", "completed");
      continue;
    }
    if (s.step === "failed") {
      seen.set(s.step, "failed");
      continue;
    }
    seen.set(s.step, s.status === "succeeded" ? "completed" : "running");
  }

  const terminalStep = stages[stages.length - 1]?.step;
  const terminalStatus = stages[stages.length - 1]?.status;

  for (const step of ALL_STEPS) {
    if (seen.has(step)) {
      const state = seen.get(step)!;
      result.push({ step, state });
    } else if (step === terminalStep && terminalStatus === "failed") {
      result.push({ step, state: "failed" });
    } else {
      result.push({ step, state: "pending" });
    }
  }

  // Mark last seen non-terminal step as running
  let lastSeenIdx = -1;
  for (let i = result.length - 1; i >= 0; i--) {
    if (result[i].state !== "pending") {
      lastSeenIdx = i;
      break;
    }
  }
  if (lastSeenIdx >= 0 && result[lastSeenIdx].state === "running") {
    // Already running, nothing to do
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
