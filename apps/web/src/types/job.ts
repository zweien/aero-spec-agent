export type JobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed";

export type JobRecord = {
  id: string;
  job_id: string;
  design_id: string;
  version_no: number;
  status: JobStatus;
  progress: number;
  current_step: string;
  error_message: string | null;
  files: Record<string, string>;
  created_at: string;
  updated_at: string;
  duration_ms: number | null;
  version_status: string;
};

export type JobPollResult = {
  id: string;
  design_id?: string;
  version_no?: number;
  status: JobStatus;
  progress?: number;
  files?: string[];
};

export function isTerminalStatus(status: string | undefined): status is "succeeded" | "failed" {
  return status === "succeeded" || status === "failed";
}

export function isSucceeded(status: string | undefined): boolean {
  return status === "succeeded";
}
