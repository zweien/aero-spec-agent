"use client";

import { useCallback, useEffect, useState } from "react";

type SettingsPanelProps = {
  apiBaseUrl: string;
};

export function SettingsPanel({ apiBaseUrl }: SettingsPanelProps) {
  const [backend, setBackend] = useState<string>("fake");
  const [vspaero, setVspaero] = useState(false);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const resp = await fetch(`${apiBaseUrl}/api/settings`);
        if (resp.ok) {
          const data = (await resp.json()) as { cad_backend: string; run_vspaero_analysis: boolean };
          setBackend(data.cad_backend);
          setVspaero(data.run_vspaero_analysis);
        }
      } catch { /* ignore */ }
    })();
  }, [apiBaseUrl]);

  const save = useCallback(
    async (updates: { cad_backend?: string; run_vspaero_analysis?: boolean }) => {
      setLoading(true);
      try {
        const resp = await fetch(`${apiBaseUrl}/api/settings`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(updates),
        });
        if (resp.ok) {
          const data = (await resp.json()) as { cad_backend: string; run_vspaero_analysis: boolean };
          setBackend(data.cad_backend);
          setVspaero(data.run_vspaero_analysis);
        }
      } catch { /* ignore */ }
      setLoading(false);
    },
    [apiBaseUrl],
  );

  return (
    <div className="settings-panel">
      <button
        type="button"
        className="settings-toggle"
        onClick={() => setOpen(!open)}
      >
        设置
      </button>
      {open && (
        <div className="settings-dropdown">
          <label className="settings-row">
            <span className="settings-label">CAD 后端</span>
            <select
              value={backend}
              disabled={loading}
              onChange={(e) => void save({ cad_backend: e.target.value })}
            >
              <option value="fake">Fake（模拟）</option>
              <option value="openvsp">OpenVSP</option>
            </select>
          </label>
          <label className="settings-row">
            <span className="settings-label">气动分析</span>
            <input
              type="checkbox"
              checked={vspaero}
              disabled={loading}
              onChange={(e) => void save({ run_vspaero_analysis: e.target.checked })}
            />
          </label>
        </div>
      )}
    </div>
  );
}
