"use client";

import React, { type JSX } from "react";

import { getStepLabel, type WorkflowStage } from "./useJobEventStream";

export type WorkflowTimelineProps = {
  stages: WorkflowStage[];
};

type StepState = "completed" | "running" | "failed" | "pending";

const STATE_CLASSES: Record<StepState, string> = {
  completed: "workflow-stage-completed status-success",
  running: "workflow-stage-running status-running",
  failed: "workflow-stage-failed status-error",
  pending: "workflow-stage-pending",
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

function statusText(state: StepState): string {
  switch (state) {
    case "completed":
      return "已完成";
    case "running":
      return "运行中";
    case "failed":
      return "失败";
    default:
      return "等待中";
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
    <ol className={"workflow-timeline"}>
      {steps.map((item, i) => {
        const isLast = i === steps.length - 1;
        const label = getStepLabel(item.step);

        return (
          <li
            key={item.step}
            className={`workflow-stage ${STATE_CLASSES[item.state]}`}
            aria-label={`${label}，状态：${statusText(item.state)}`}
          >
            <div className="workflow-stage-row">
              <span className="workflow-stage-indicator workflow-stage-indicator-large" aria-hidden="true">
                {circleIcon(item.state)}
              </span>
              <span className="workflow-stage-label">
                {label}
              </span>
            </div>

            {!isLast && (
              <div className="workflow-stage-rail workflow-stage-rail-large" aria-hidden="true" />
            )}
          </li>
        );
      })}
    </ol>
  );
}
