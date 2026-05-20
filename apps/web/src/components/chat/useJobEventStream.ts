import type { JobPollResult } from "@/types/job";

export type WorkflowStage = {
  eventType?: string;
  step: string;
  progress: number;
  status: string;
  timestamp: string;
  error_message?: string;
  duration_ms?: number;
  files?: Record<string, string>;
  version_no?: number;
  stage?: string;
  label?: string;
  artifact?: string;
  metadata?: Record<string, unknown>;
};

export type DefaultedField = { path: string; label: string; value: number | string; unit?: string; reason: string };

export type JobStreamResult = {
  stages: WorkflowStage[];
  finalStatus: "succeeded" | "failed" | "timeout";
  files?: Record<string, string>;
  version_no?: number;
  design_id?: string;
  duration_ms?: number;
  error_message?: string;
  defaulted_fields?: DefaultedField[];
};

type StreamOptions = {
  apiBaseUrl: string;
  jobId: string;
  onStage?: (stage: WorkflowStage) => void;
  signal?: AbortSignal;
};

function parseSseEvents(buffer: string): { events: Array<{ type: string; data: string }>; rest: string } {
  const events: Array<{ type: string; data: string }> = [];
  let rest = buffer;

  while (true) {
    const endIdx = rest.indexOf("\n\n");
    if (endIdx === -1) break;

    const block = rest.slice(0, endIdx);
    rest = rest.slice(endIdx + 2);

    let eventType = "";
    let data = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) {
        eventType = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        data = line.slice(5).trimStart();
      }
    }
    if (eventType && data) {
      events.push({ type: eventType, data });
    }
  }

  return { events, rest };
}

const STEP_LABELS: Record<string, string> = {
  writing_spec: "编写设计规格",
  geometry_building: "构建几何模型",
  mesh_export: "导出三维模型",
  report_generating: "生成分析报告",
  generating_cad: "生成 CAD 模型",
  succeeded: "设计完成",
  failed: "生成失败",
};

export function getStepLabel(step: string): string {
  return STEP_LABELS[step] ?? step;
}

const TERMINAL_EVENTS = new Set(["generation_complete", "generation_failed"]);

export async function streamJobEvents(opts: StreamOptions): Promise<JobStreamResult> {
  const { apiBaseUrl, jobId, onStage, signal } = opts;
  const stages: WorkflowStage[] = [];

  const response = await fetch(`${apiBaseUrl}/api/jobs/${jobId}/stream`, { signal });
  if (!response.ok || !response.body) {
    throw new Error(`Job stream failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const { events, rest } = parseSseEvents(buffer);
    buffer = rest;

    for (const evt of events) {
      try {
        const parsed = JSON.parse(evt.data);

        if (evt.type === "workflow_stage") {
          const stage: WorkflowStage = {
            eventType: evt.type,
            step: parsed.current_step ?? parsed.stage ?? "",
            progress: parsed.progress ?? 0,
            status: parsed.status ?? "running",
            timestamp: parsed.timestamp ?? "",
            stage: parsed.stage ?? "",
            label: parsed.label ?? "",
            metadata: parsed.metadata,
          };
          stages.push(stage);
          onStage?.(stage);
          continue; // Not terminal, continue processing
        }

        if (evt.type === "artifact_generated") {
          const artifactKey = parsed.artifact ?? parsed.metadata?.artifact_key ?? "";
          const stage: WorkflowStage = {
            eventType: evt.type,
            step: parsed.current_step ?? `artifact_${artifactKey}`,
            progress: parsed.progress ?? 0,
            status: parsed.status ?? "running",
            timestamp: parsed.timestamp ?? "",
            label: parsed.label ?? "",
            artifact: artifactKey,
            metadata: parsed.metadata,
          };
          stages.push(stage);
          onStage?.(stage);
          continue; // Not terminal, continue processing
        }

        if (TERMINAL_EVENTS.has(evt.type)) {
          const isFailed = evt.type === "generation_failed";
          return {
            stages,
            finalStatus: isFailed ? "failed" : "succeeded",
            files: parsed.files,
            version_no: parsed.version_no,
            design_id: parsed.design_id ?? undefined,
            duration_ms: parsed.duration_ms,
            error_message: parsed.error_message,
            defaulted_fields: Array.isArray(parsed.metadata?.defaulted_fields)
              ? parsed.metadata.defaulted_fields as DefaultedField[]
              : undefined,
          };
        }

        const stage: WorkflowStage = {
          eventType: evt.type,
          step: parsed.current_step ?? "",
          progress: parsed.progress ?? 0,
          status: parsed.status ?? "running",
          timestamp: parsed.timestamp ?? "",
        };
        if (parsed.error_message) stage.error_message = parsed.error_message;
        if (parsed.duration_ms != null) stage.duration_ms = parsed.duration_ms;
        if (parsed.files) stage.files = parsed.files;
        if (parsed.version_no) stage.version_no = parsed.version_no;

        stages.push(stage);
        onStage?.(stage);
      } catch {
        // Skip malformed JSON
      }
    }
  }

  return { stages, finalStatus: "timeout" };
}

export function toJobPollResult(result: JobStreamResult, jobId: string): JobPollResult {
  const last = result.stages[result.stages.length - 1];
  return {
    id: jobId,
    design_id: result.design_id,
    version_no: result.version_no ?? last?.version_no,
    status: result.finalStatus === "succeeded" ? "succeeded" : "failed",
    progress: last?.progress,
    files: result.files ? Object.keys(result.files) : undefined,
  };
}
