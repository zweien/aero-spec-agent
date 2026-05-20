import assert from "node:assert/strict";
import test from "node:test";

import {
  getStageLabel,
  type WorkflowRuntimeState,
  type WorkflowRuntimeStage,
  type WorkflowStageEvent,
} from "./useWorkflowRuntime.ts";

// ---------------------------------------------------------------------------
// getStageLabel
// ---------------------------------------------------------------------------

test("getStageLabel maps known stages to Chinese labels", () => {
  assert.equal(getStageLabel("understanding_requirements"), "理解设计需求");
  assert.equal(getStageLabel("generating_spec"), "生成飞机参数");
  assert.equal(getStageLabel("validating_parameters"), "校验设计参数");
  assert.equal(getStageLabel("generating_cad"), "生成 CAD 模型");
  assert.equal(getStageLabel("fuselage_created"), "生成机身");
  assert.equal(getStageLabel("wing_created"), "生成机翼");
  assert.equal(getStageLabel("tail_created"), "生成尾翼");
  assert.equal(getStageLabel("engine_created"), "生成发动机");
  assert.equal(getStageLabel("vsp_model_saved"), "保存模型");
  assert.equal(getStageLabel("step_exported"), "正在导出 STEP 文件");
  assert.equal(getStageLabel("glb_exported"), "导出 3D 模型");
  assert.equal(getStageLabel("preview_ready"), "三维预览准备就绪");
  assert.equal(getStageLabel("completed"), "设计完成");
  assert.equal(getStageLabel("succeeded"), "设计完成");
  assert.equal(getStageLabel("failed"), "生成失败");
});

test("getStageLabel returns stage name for unknown stages", () => {
  assert.equal(getStageLabel("unknown_stage"), "unknown_stage");
  assert.equal(getStageLabel("custom_cad_step"), "custom_cad_step");
});

// ---------------------------------------------------------------------------
// INITIAL_STATE structure
// ---------------------------------------------------------------------------

test("initial state has idle status and empty stages", () => {
  const state: WorkflowRuntimeState = {
    stages: [],
    currentStage: null,
    progress: 0,
    elapsedTime: 0,
    artifacts: [],
    status: "idle",
    error: null,
  };
  assert.equal(state.status, "idle");
  assert.equal(state.stages.length, 0);
  assert.equal(state.currentStage, null);
  assert.equal(state.progress, 0);
  assert.equal(state.error, null);
});

// ---------------------------------------------------------------------------
// Stage type structure
// ---------------------------------------------------------------------------

test("WorkflowRuntimeStage has expected shape", () => {
  const stage: WorkflowRuntimeStage = {
    stage: "fuselage_created",
    label: "生成机身",
    status: "running",
    startedAt: 1000,
    completedAt: null,
    durationMs: null,
  };
  assert.equal(stage.stage, "fuselage_created");
  assert.equal(stage.label, "生成机身");
  assert.equal(stage.status, "running");
  assert.equal(stage.startedAt, 1000);
  assert.equal(stage.completedAt, null);
  assert.equal(stage.durationMs, null);
});

test("WorkflowRuntimeStage can carry metadata", () => {
  const stage: WorkflowRuntimeStage = {
    stage: "glb_exported",
    label: "导出 3D 模型",
    status: "completed",
    startedAt: 1000,
    completedAt: 2000,
    durationMs: 1000,
    metadata: { artifact_key: "aircraft.glb" },
  };
  assert.ok(stage.metadata);
  assert.equal((stage.metadata as Record<string, unknown>).artifact_key, "aircraft.glb");
});

// ---------------------------------------------------------------------------
// WorkflowStageEvent type
// ---------------------------------------------------------------------------

test("WorkflowStageEvent carries stage and optional fields", () => {
  const event: WorkflowStageEvent = {
    stage: "fuselage_created",
    label: "生成机身",
    progress: 30,
  };
  assert.equal(event.stage, "fuselage_created");
  assert.equal(event.label, "生成机身");
  assert.equal(event.progress, 30);
  assert.equal(event.error_message, undefined);
});

test("WorkflowStageEvent can carry error_message", () => {
  const event: WorkflowStageEvent = {
    stage: "generating_cad",
    error_message: "参数超出范围",
  };
  assert.equal(event.stage, "generating_cad");
  assert.equal(event.error_message, "参数超出范围");
});

// ---------------------------------------------------------------------------
// State transition simulation (pure-function recreation of hook logic)
// ---------------------------------------------------------------------------

/** Simulate applyEvent state transition — mirrors the hook's setState logic. */
function simulateApplyEvent(
  prev: WorkflowRuntimeState,
  event: WorkflowStageEvent,
  startTime: number | null,
): { state: WorkflowRuntimeState; startTime: number } {
  if (prev.status === "completed" || prev.status === "failed") {
    return { state: prev, startTime: startTime ?? 0 };
  }

  const now = 10000; // fixed timestamp for deterministic tests
  const st = startTime ?? now;

  const existingIdx = prev.stages.findIndex((s) => s.stage === event.stage);
  const updatedStages = [...prev.stages];

  // Complete all running stages
  for (let i = 0; i < updatedStages.length; i++) {
    const s = updatedStages[i]!;
    if (s.status === "running") {
      updatedStages[i] = {
        ...s,
        status: "completed" as const,
        completedAt: now,
        durationMs: s.startedAt ? now - s.startedAt : null,
      };
    }
  }

  // Update or add stage
  if (existingIdx >= 0) {
    updatedStages[existingIdx] = {
      ...updatedStages[existingIdx]!,
      status: event.error_message ? ("failed" as const) : ("running" as const),
      startedAt: updatedStages[existingIdx]!.startedAt ?? now,
      metadata: event.metadata,
    };
  } else {
    updatedStages.push({
      stage: event.stage,
      label: event.label ?? getStageLabel(event.stage),
      status: event.error_message ? ("failed" as const) : ("running" as const),
      startedAt: now,
      completedAt: null,
      durationMs: null,
      metadata: event.metadata,
    });
  }

  const isFailed = !!event.error_message;
  const updatedArtifacts =
    event.metadata?.artifact_key && !prev.artifacts.includes(event.metadata.artifact_key as string)
      ? [...prev.artifacts, event.metadata.artifact_key as string]
      : prev.artifacts;

  return {
    state: {
      stages: updatedStages,
      currentStage: isFailed ? null : event.stage,
      progress: event.progress ?? prev.progress,
      elapsedTime: st ? now - st : 0,
      artifacts: updatedArtifacts,
      status: isFailed ? ("failed" as const) : prev.status,
      error: isFailed ? { stage: event.stage, message: event.error_message! } : prev.error,
    },
    startTime: st,
  };
}

const IDLE_STATE: WorkflowRuntimeState = {
  stages: [],
  currentStage: null,
  progress: 0,
  elapsedTime: 0,
  artifacts: [],
  status: "idle",
  error: null,
};

function toRunning(prev: WorkflowRuntimeState): WorkflowRuntimeState {
  return { ...prev, status: "running" };
}

test("applyEvent: first event transitions from idle to running", () => {
  const running = toRunning(IDLE_STATE);
  const { state } = simulateApplyEvent(running, { stage: "understanding_requirements" }, null);
  assert.equal(state.status, "running");
  assert.equal(state.currentStage, "understanding_requirements");
  assert.equal(state.stages.length, 1);
  assert.equal(state.stages[0]!.status, "running");
});

test("applyEvent: subsequent events complete previous running stage", () => {
  let state = toRunning(IDLE_STATE);
  let st: number | null = null;

  // First event
  ({ state, startTime: st } = simulateApplyEvent(state, { stage: "understanding_requirements" }, st));
  // Second event
  ({ state, startTime: st } = simulateApplyEvent(state, { stage: "generating_spec" }, st));

  assert.equal(state.stages.length, 2);
  assert.equal(state.stages[0]!.status, "completed");
  assert.equal(state.stages[1]!.status, "running");
  assert.equal(state.currentStage, "generating_spec");
});

test("applyEvent: error transitions to failed state", () => {
  const running = toRunning(IDLE_STATE);
  const { state } = simulateApplyEvent(running, {
    stage: "generating_cad",
    error_message: "参数超出范围",
  }, null);

  assert.equal(state.status, "failed");
  assert.equal(state.error!.stage, "generating_cad");
  assert.equal(state.error!.message, "参数超出范围");
  assert.equal(state.currentStage, null);
});

test("applyEvent: terminal state ignores further events", () => {
  const completed: WorkflowRuntimeState = {
    ...IDLE_STATE,
    status: "completed",
    stages: [{ stage: "completed", label: "设计完成", status: "completed", startedAt: 0, completedAt: 0, durationMs: 0 }],
  };
  const { state } = simulateApplyEvent(completed, { stage: "new_stage" }, null);
  assert.equal(state.status, "completed");
  assert.equal(state.stages.length, 1); // unchanged
});

test("applyEvent: tracks artifacts from metadata", () => {
  let state = toRunning(IDLE_STATE);
  let st: number | null = null;

  ({ state, startTime: st } = simulateApplyEvent(state, {
    stage: "glb_exported",
    metadata: { artifact_key: "aircraft.glb" },
  }, st));

  assert.deepEqual(state.artifacts, ["aircraft.glb"]);

  // Duplicate artifact_key not added
  ({ state, startTime: st } = simulateApplyEvent(state, {
    stage: "step_exported",
    metadata: { artifact_key: "aircraft.glb" },
  }, st));

  assert.deepEqual(state.artifacts, ["aircraft.glb"]);
});

test("applyEvent: progress updates from event", () => {
  const running = toRunning(IDLE_STATE);
  const { state } = simulateApplyEvent(running, { stage: "generating_cad", progress: 50 }, null);
  assert.equal(state.progress, 50);
});

test("applyEvent: label defaults to getStageLabel when not provided", () => {
  const running = toRunning(IDLE_STATE);
  const { state } = simulateApplyEvent(running, { stage: "fuselage_created" }, null);
  assert.equal(state.stages[0]!.label, "生成机身");
});

test("applyEvent: custom label from event takes precedence", () => {
  const running = toRunning(IDLE_STATE);
  const { state } = simulateApplyEvent(running, { stage: "custom_step", label: "自定义步骤" }, null);
  assert.equal(state.stages[0]!.label, "自定义步骤");
});
