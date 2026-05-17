import type { JobStatus, JobPollResult } from "@/types/job";

export type { JobStatus, JobPollResult };

type GenerationJob = {
  id: string;
  design_id?: string;
  version_no?: number;
  status?: JobStatus;
  progress?: number;
  current_step?: string;
  error_message?: string | null;
  files?: Record<string, string> | string[];
};

type WaitForGenerationJobOptions = {
  apiBaseUrl: string;
  jobId: string;
  intervalMs?: number;
  maxAttempts?: number;
  fetchFn?: typeof fetch;
};

export async function waitForGenerationJob({
  apiBaseUrl,
  jobId,
  intervalMs = 1000,
  maxAttempts = 120,
  fetchFn = fetch,
}: WaitForGenerationJobOptions): Promise<JobPollResult> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const response = await fetchFn(`${apiBaseUrl}/api/jobs/${jobId}`);
    if (!response.ok) {
      throw new Error(`Job API failed with status ${response.status}`);
    }

    const job = (await response.json()) as GenerationJob;
    if (job.status === "failed") {
      throw new Error(job.error_message ?? "生成任务失败");
    }
    if (job.status === "succeeded") {
      return normalizeJobResult(job);
    }

    if (attempt < maxAttempts - 1) {
      await delay(intervalMs);
    }
  }

  throw new Error("生成任务超时");
}

function normalizeJobResult(job: GenerationJob): JobPollResult {
  return {
    id: job.id,
    design_id: job.design_id,
    version_no: job.version_no,
    status: job.status ?? "succeeded",
    progress: job.progress,
    files: normalizeFiles(job.files),
  };
}

function normalizeFiles(files: GenerationJob["files"]): string[] | undefined {
  if (Array.isArray(files)) return files;
  if (files && typeof files === "object") return Object.keys(files);
  return undefined;
}

function delay(ms: number): Promise<void> {
  if (ms <= 0) return Promise.resolve();
  return new Promise((resolve) => globalThis.setTimeout(resolve, ms));
}
