"use client";

import { useCallback, useState } from "react";

import {
  fetchJobDiagnostics,
  type JobDiagnostics,
} from "@/lib/jobDiagnostics";

type DiagnosticsPanelProps = {
  apiBaseUrl: string;
  jobId: string;
};

export function DiagnosticsPanel({ apiBaseUrl, jobId }: DiagnosticsPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [data, setData] = useState<JobDiagnostics | null>(null);
  const [loading, setLoading] = useState(false);

  const handleToggle = useCallback(async () => {
    if (expanded) {
      setExpanded(false);
      return;
    }
    if (loading) return;
    setLoading(true);
    const result = await fetchJobDiagnostics(apiBaseUrl, jobId);
    setData(result);
    setLoading(false);
    setExpanded(true);
  }, [apiBaseUrl, jobId, expanded, loading]);

  return (
    <div className="tool-card-diagnostics">
      <button
        type="button"
        className="tool-card-toggle"
        onClick={handleToggle}
        disabled={loading}
      >
        {loading ? "加载中..." : expanded ? "▾ 收起诊断" : "▸ 查看诊断"}
      </button>
      {expanded && data && (
        <pre className="tool-card-diag-content">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}
