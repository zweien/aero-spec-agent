"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getLlmSettings,
  getProfiles,
  getActiveProfileId,
  setActiveProfileId,
  addProfile,
  removeProfile,
  updateProfile,
  PRESET_TEMPLATES,
  type LlmProfile,
} from "@/lib/llmSettings";

type LlmTestStatus = "idle" | "testing" | "ok" | "fail";

type SettingsPanelProps = {
  apiBaseUrl: string;
};

export function SettingsPanel({ apiBaseUrl }: SettingsPanelProps) {
  const [backend, setBackend] = useState<string>("fake");
  const [vspaero, setVspaero] = useState(false);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  // LLM settings
  const [llmModel, setLlmModel] = useState("");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [llmBaseUrl, setLlmBaseUrl] = useState("");
  const [llmTestStatus, setLlmTestStatus] = useState<LlmTestStatus>("idle");
  const [llmTestMsg, setLlmTestMsg] = useState("");

  // Profile management
  const [profiles, setProfiles] = useState<LlmProfile[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [showAddForm, setShowAddForm] = useState(false);
  const [newName, setNewName] = useState("");

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

    // Load profiles and active settings
    const p = getProfiles();
    setProfiles(p);
    const aid = getActiveProfileId() ?? "";
    setActiveId(aid);
    const settings = getLlmSettings();
    setLlmModel(settings.modelName);
    setLlmApiKey(settings.apiKey);
    setLlmBaseUrl(settings.baseUrl);
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

  const saveLlm = useCallback(() => {
    if (activeId) {
      updateProfile(activeId, { modelName: llmModel, apiKey: llmApiKey, baseUrl: llmBaseUrl });
    }
  }, [activeId, llmModel, llmApiKey, llmBaseUrl]);

  const handleSelectProfile = useCallback((id: string) => {
    setActiveProfileId(id);
    setActiveId(id);
    const p = getProfiles().find((p) => p.id === id);
    if (p) {
      setLlmModel(p.modelName);
      setLlmApiKey(p.apiKey);
      setLlmBaseUrl(p.baseUrl);
    }
  }, []);

  const handleAddProfile = useCallback(() => {
    if (!newName.trim()) return;
    const p = addProfile(newName.trim(), { modelName: llmModel, apiKey: llmApiKey, baseUrl: llmBaseUrl });
    setProfiles(getProfiles());
    setActiveId(p.id);
    setShowAddForm(false);
    setNewName("");
  }, [newName, llmModel, llmApiKey, llmBaseUrl]);

  const handleRemoveProfile = useCallback(() => {
    if (!activeId) return;
    removeProfile(activeId);
    const updated = getProfiles();
    setProfiles(updated);
    if (updated.length > 0) {
      handleSelectProfile(updated[0].id);
    } else {
      setActiveId("");
      setLlmModel("");
      setLlmApiKey("");
      setLlmBaseUrl("");
    }
  }, [activeId, handleSelectProfile]);

  const handlePreset = useCallback((template: { modelName: string; baseUrl: string }) => {
    setLlmModel(template.modelName);
    setLlmBaseUrl(template.baseUrl);
    if (!showAddForm && activeId) {
      updateProfile(activeId, { modelName: template.modelName, baseUrl: template.baseUrl });
    }
  }, [activeId, showAddForm]);

  const testLlm = useCallback(async () => {
    if (!llmApiKey && !llmBaseUrl) {
      setLlmTestStatus("fail");
      setLlmTestMsg("请先填写 API Key 或 Base URL");
      return;
    }
    saveLlm();
    setLlmTestStatus("testing");
    setLlmTestMsg("");
    try {
      const resp = await fetch("/api/llm-test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          modelName: llmModel || undefined,
          apiKey: llmApiKey || undefined,
          baseUrl: llmBaseUrl || undefined,
        }),
      });
      const data = (await resp.json()) as { ok: boolean; error?: string };
      if (data.ok) {
        setLlmTestStatus("ok");
        setLlmTestMsg("连接成功");
      } else {
        setLlmTestStatus("fail");
        setLlmTestMsg(data.error ?? `HTTP ${resp.status}`);
      }
    } catch (err) {
      setLlmTestStatus("fail");
      setLlmTestMsg(err instanceof Error ? err.message : "连接失败");
    }
  }, [llmModel, llmApiKey, llmBaseUrl, saveLlm]);

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
          <div className="settings-section-title">CAD 后端</div>
          <label className="settings-row">
            <span className="settings-label">后端</span>
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

          <div className="settings-section-title" style={{ marginTop: 8 }}>LLM 配置</div>

          {/* Profile selector */}
          <div className="settings-row" style={{ gap: 4 }}>
            <select
              value={activeId}
              onChange={(e) => handleSelectProfile(e.target.value)}
              style={{ flex: 1, fontSize: 11 }}
            >
              <option value="">（默认）</option>
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => setShowAddForm(!showAddForm)}
              style={{ fontSize: 11, padding: "2px 6px", cursor: "pointer" }}
              title="添加配置"
            >
              +
            </button>
            {activeId && profiles.length > 0 && (
              <button
                type="button"
                onClick={handleRemoveProfile}
                style={{ fontSize: 11, padding: "2px 6px", cursor: "pointer", color: "var(--error)" }}
                title="删除当前配置"
              >
                &times;
              </button>
            )}
          </div>

          {/* Add profile form */}
          {showAddForm && (
            <div className="settings-row" style={{ gap: 4 }}>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="配置名称"
                style={{ flex: 1, fontSize: 11 }}
                onKeyDown={(e) => { if (e.key === "Enter") handleAddProfile(); }}
              />
              <button
                type="button"
                onClick={handleAddProfile}
                disabled={!newName.trim()}
                style={{ fontSize: 11, padding: "2px 8px", cursor: "pointer" }}
              >
                保存
              </button>
            </div>
          )}

          {/* Quick-fill presets */}
          <div className="settings-row" style={{ gap: 4, flexWrap: "wrap" }}>
            {PRESET_TEMPLATES.map((t) => (
              <button
                key={t.name}
                type="button"
                onClick={() => handlePreset(t)}
                style={{
                  fontSize: 10,
                  padding: "2px 6px",
                  border: "1px solid var(--border-default)",
                  borderRadius: 3,
                  background: "transparent",
                  cursor: "pointer",
                  color: "var(--text-dim)",
                }}
              >
                {t.name}
              </button>
            ))}
          </div>

          {/* LLM fields */}
          <label className="settings-row">
            <span className="settings-label">模型</span>
            <input
              type="text"
              value={llmModel}
              onChange={(e) => setLlmModel(e.target.value)}
              onBlur={saveLlm}
              placeholder="留空使用默认"
              style={{ width: 120 }}
            />
          </label>
          <label className="settings-row">
            <span className="settings-label">API Key</span>
            <input
              type="password"
              value={llmApiKey}
              onChange={(e) => setLlmApiKey(e.target.value)}
              onBlur={saveLlm}
              placeholder="留空使用默认"
              style={{ width: 120 }}
            />
          </label>
          <label className="settings-row">
            <span className="settings-label">Base URL</span>
            <input
              type="text"
              value={llmBaseUrl}
              onChange={(e) => setLlmBaseUrl(e.target.value)}
              onBlur={saveLlm}
              placeholder="留空使用默认"
              style={{ width: 120 }}
            />
          </label>
          <div className="settings-row" style={{ justifyContent: "flex-end" }}>
            {llmTestMsg && (
              <span className={`llm-test-result ${llmTestStatus === "ok" ? "llm-test-ok" : "llm-test-fail"}`}>
                {llmTestMsg}
              </span>
            )}
            <button
              type="button"
              className="llm-test-btn"
              disabled={llmTestStatus === "testing"}
              onClick={() => void testLlm()}
            >
              {llmTestStatus === "testing" ? "测试中…" : "测试连接"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
