import type { JobPollResult } from "@/types/job";
import { waitForGenerationJob } from "@/components/chat/jobPolling";

export type GenerationFlowResult = {
  status: string;
  design_id?: string;
  version_no?: number;
  files?: string[];
  error_message?: string;
};

/**
 * Poll a job to completion and return a unified result.
 *
 * If the job is already succeeded, skip polling.
 * Returns a rejected promise on failure so callers can .catch().
 */
export async function pollJobToCompletion(opts: {
  apiBaseUrl: string;
  jobId: string;
  initialStatus?: string;
  design_id?: string;
  version_no?: number;
  files?: Record<string, string>;
}): Promise<GenerationFlowResult> {
  const { apiBaseUrl, jobId, initialStatus, design_id, version_no, files } = opts;

  if (initialStatus === "succeeded") {
    return {
      status: "succeeded",
      design_id,
      version_no,
      files: files ? Object.keys(files) : undefined,
    };
  }

  const result: JobPollResult = await waitForGenerationJob({ apiBaseUrl, jobId });
  return {
    status: result.status,
    design_id: result.design_id,
    version_no: result.version_no,
    files: result.files,
  };
}
