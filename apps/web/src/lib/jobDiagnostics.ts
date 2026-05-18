export type JobDiagnostics = {
  job: Record<string, unknown>;
  version_status: Record<string, unknown> | null;
  generation_log: Record<string, unknown> | null;
  validation_report: Record<string, unknown> | null;
  files_exist: Record<string, boolean>;
};

export async function fetchJobDiagnostics(
  apiBaseUrl: string,
  jobId: string,
  fetchFn: typeof fetch = fetch,
): Promise<JobDiagnostics | null> {
  try {
    const resp = await fetchFn(`${apiBaseUrl}/api/jobs/${jobId}/diagnostics`);
    if (resp.ok) {
      return (await resp.json()) as JobDiagnostics;
    }
    return null;
  } catch {
    return null;
  }
}
