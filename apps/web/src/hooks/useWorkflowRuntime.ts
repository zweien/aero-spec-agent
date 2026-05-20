"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// --- Types ---

export type StageStatus = "completed" | "running" | "pending" | "failed";

export type WorkflowRuntimeStage = {
  stage: string;
  label: string;
  status: StageStatus;
  startedAt: number | null;
  completedAt: number | null;
  durationMs: number | null;
  metadata?: Record<string, unknown>;
};

export type WorkflowRuntimeState = {
  stages: WorkflowRuntimeStage[];
  currentStage: string | null;
  progress: number;
  elapsedTime: number;
  artifacts: string[];
  status: "idle" | "running" | "completed" | "failed";
  error: { stage: string; message: string } | null;
};

export type WorkflowStageEvent = {
  stage: string;
  label?: string;
  progress?: number;
  status?: string;
  metadata?: Record<string, unknown>;
  error_message?: string;
};

// --- Label Mapping ---

const STAGE_LABELS: Record<string, string> = {
  // Preliminary stages (LLM thinking phase)
  understanding_requirements: "理解设计需求",
  generating_spec: "生成飞机参数",
  validating_parameters: "校验设计参数",
  generating_cad: "生成 CAD 模型",
  // CAD sub-stages
  fuselage_created: "生成机身",
  wing_created: "生成机翼",
  tail_created: "生成尾翼",
  engine_created: "生成发动机",
  vsp_model_saved: "保存模型",
  step_exported: "正在导出 STEP 文件",
  glb_exported: "导出 3D 模型",
  preview_ready: "三维预览准备就绪",
  // Legacy step names (backward compat)
  writing_spec: "生成飞机参数",
  geometry_building: "构建几何模型",
  mesh_export: "导出三维模型",
  report_generating: "生成分析报告",
  // Terminal
  succeeded: "设计完成",
  completed: "设计完成",
  failed: "生成失败",
};

export function getStageLabel(stage: string): string {
  return STAGE_LABELS[stage] ?? stage;
}

// --- Hook ---

const INITIAL_STATE: WorkflowRuntimeState = {
  stages: [],
  currentStage: null,
  progress: 0,
  elapsedTime: 0,
  artifacts: [],
  status: "idle",
  error: null,
};

export function useWorkflowRuntime() {
  const [state, setState] = useState<WorkflowRuntimeState>(INITIAL_STATE);
  const startTimeRef = useRef<number | null>(null);

  // Tick elapsedTime + preliminary progress every ~200ms while running
  useEffect(() => {
    if (state.status !== "running" || !startTimeRef.current) return;
    const id = setInterval(() => {
      const now = Date.now();
      setState((prev) => {
        if (prev.status !== "running" || !startTimeRef.current) return prev;
        const elapsed = now - startTimeRef.current!;
        // During preliminary phase (no real stages completed yet), simulate progress 0→45%
        const progress = prev.progress < 46
          ? Math.min(45, Math.round(elapsed / 100))
          : prev.progress;
        return { ...prev, elapsedTime: elapsed, progress };
      });
    }, 200);
    return () => clearInterval(id);
  }, [state.status]);

  const reset = useCallback(() => {
    setState(INITIAL_STATE);
    startTimeRef.current = null;
  }, []);

  const applyPreliminaryStages = useCallback((stages: string[]) => {
    const now = Date.now();
    startTimeRef.current = now;
    const runtimeStages: WorkflowRuntimeStage[] = stages.map((stage, i) => ({
      stage,
      label: getStageLabel(stage),
      status: (i === stages.length - 1 ? "running" : "pending") as StageStatus,
      startedAt: i === stages.length - 1 ? now : null,
      completedAt: null,
      durationMs: null,
    }));
    // Mark first stage as completed if there are multiple stages
    if (runtimeStages.length > 1) {
      runtimeStages[0].status = "running";
    }
    setState({
      stages: runtimeStages,
      currentStage: stages[stages.length - 1],
      progress: 0,
      elapsedTime: 0,
      artifacts: [],
      status: "running",
      error: null,
    });
  }, []);

  const transitionToRealStages = useCallback(() => {
    setState((prev) => {
      // Clear preliminary stages — real stages will be added by applyEvent
      return {
        ...prev,
        stages: [],
        currentStage: null,
      };
    });
  }, []);

  const applyEvent = useCallback((event: WorkflowStageEvent) => {
    setState((prev) => {
      if (prev.status === "completed" || prev.status === "failed") return prev;

      const now = Date.now();
      if (!startTimeRef.current) startTimeRef.current = now;

      // Mark all previous stages as completed
      const existingIdx = prev.stages.findIndex((s) => s.stage === event.stage);
      const updatedStages = [...prev.stages];

      // Complete all stages before this one that are still running
      for (let i = 0; i < updatedStages.length; i++) {
        const s = updatedStages[i]!;
        if (s.status === "running") {
          updatedStages[i] = {
            ...s,
            status: "completed",
            completedAt: now,
            durationMs: s.startedAt ? now - s.startedAt : null,
          };
        }
      }

      // Update or add this stage
      if (existingIdx >= 0) {
        updatedStages[existingIdx] = {
          ...updatedStages[existingIdx],
          status: event.error_message ? "failed" : "running",
          startedAt: updatedStages[existingIdx].startedAt ?? now,
          metadata: event.metadata,
        };
      } else {
        updatedStages.push({
          stage: event.stage,
          label: event.label ?? getStageLabel(event.stage),
          status: event.error_message ? "failed" : "running",
          startedAt: now,
          completedAt: null,
          durationMs: null,
          metadata: event.metadata,
        });
      }

      const isFailed = !!event.error_message;
      const newStatus = isFailed ? "failed" : prev.status;

      // Track artifacts from artifact_generated events
      const updatedArtifacts =
        event.metadata?.artifact_key && !prev.artifacts.includes(event.metadata.artifact_key as string)
          ? [...prev.artifacts, event.metadata.artifact_key as string]
          : prev.artifacts;

      return {
        stages: updatedStages,
        currentStage: isFailed ? null : event.stage,
        progress: event.progress ?? prev.progress,
        elapsedTime: startTimeRef.current ? now - startTimeRef.current : 0,
        artifacts: updatedArtifacts,
        status: newStatus,
        error: isFailed ? { stage: event.stage, message: event.error_message! } : prev.error,
      };
    });
  }, []);

  const markCompleted = useCallback((files?: string[]) => {
    setState((prev) => {
      const now = Date.now();
      const stages = prev.stages.map((s) => {
        if (s.status === "running") {
          return { ...s, status: "completed" as StageStatus, completedAt: now, durationMs: s.startedAt ? now - s.startedAt : null };
        }
        return s;
      });
      // Add completed stage if not already present
      if (!stages.some((s) => s.stage === "completed")) {
        stages.push({
          stage: "completed",
          label: getStageLabel("completed"),
          status: "completed",
          startedAt: now,
          completedAt: now,
          durationMs: 0,
        });
      }
      return {
        stages,
        currentStage: null,
        progress: 100,
        elapsedTime: startTimeRef.current ? now - startTimeRef.current : 0,
        artifacts: files ?? prev.artifacts,
        status: "completed",
        error: null,
      };
    });
  }, []);

  return { state, applyEvent, applyPreliminaryStages, transitionToRealStages, markCompleted, reset };
}
