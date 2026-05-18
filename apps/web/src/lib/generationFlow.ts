import type { JobStatus, JobPollResult } from "../types/job.ts";
import { waitForGenerationJob } from "../components/chat/jobPolling.ts";

export type GenerationFlowResult = {
  status: JobStatus;
  design_id?: string;
  version_no?: number;
  files?: string[];
  error_message?: string | null;
};

/**
 * Resolve a generation job by polling the backend.
 *
 * Throws immediately if jobId is empty.
 * Returns a rejected promise if the job fails (waitForGenerationJob throws).
 */
export async function resolveGenerationJob(opts: {
  apiBaseUrl: string;
  jobId: string;
}): Promise<JobPollResult> {
  if (!opts.jobId) {
    throw new Error("缺少 job_id，无法轮询生成任务");
  }
  return waitForGenerationJob({
    apiBaseUrl: opts.apiBaseUrl,
    jobId: opts.jobId,
  });
}

/**
 * High-level: poll a job to completion and return a unified result.
 *
 * If the job is already succeeded (from initial response), skip polling.
 * Otherwise call resolveGenerationJob to poll.
 */
export async function pollJobToCompletion(opts: {
  apiBaseUrl: string;
  jobId: string;
  initialStatus?: string;
  design_id?: string;
  version_no?: number;
  files?: Record<string, string>;
  error_message?: string | null;
}): Promise<GenerationFlowResult> {
  const { apiBaseUrl, jobId, initialStatus, design_id, version_no, files, error_message } = opts;

  if (!jobId) {
    throw new Error("缺少 job_id，无法轮询生成任务");
  }

  if (initialStatus === "succeeded") {
    return {
      status: "succeeded",
      design_id,
      version_no,
      files: files ? Object.keys(files) : undefined,
      error_message,
    };
  }

  const result = await resolveGenerationJob({ apiBaseUrl, jobId });
  return {
    status: result.status,
    design_id: result.design_id,
    version_no: result.version_no,
    files: result.files,
  };
}
