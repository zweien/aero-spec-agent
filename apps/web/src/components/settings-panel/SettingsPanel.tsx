"use client";

import { useCallback, useEffect, useState } from "react";
import { getLlmSettings, saveLlmSettings } from "@/lib/llmSettings";

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

    // Load LLM settings from localStorage
    const llm = getLlmSettings();
    setLlmModel(llm.modelName);
    setLlmApiKey(llm.apiKey);
    setLlmBaseUrl(llm.baseUrl);
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
    saveLlmSettings({
      modelName: llmModel,
      apiKey: llmApiKey,
      baseUrl: llmBaseUrl,
    });
  }, [llmModel, llmApiKey, llmBaseUrl]);

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
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_id: "__test__",
          message: "hi",
          messages: [{ id: "t1", role: "user", parts: [{ type: "text", text: "hi" }] }],
          llm_settings: {
            modelName: llmModel || undefined,
            apiKey: llmApiKey || undefined,
            baseUrl: llmBaseUrl || undefined,
          },
        }),
      });
      if (!resp.ok) {
        const err = await resp.text().catch(() => "");
        setLlmTestStatus("fail");
        setLlmTestMsg(resp.status === 400 ? "缺少 API Key" : `HTTP ${resp.status}: ${err.slice(0, 80)}`);
        return;
      }
      // Read a small chunk to confirm the LLM responded
      const reader = resp.body!.getReader();
      const { value } = await reader.read();
      reader.cancel();
      if (value && value.length > 0) {
        setLlmTestStatus("ok");
        setLlmTestMsg("连接成功");
      } else {
        setLlmTestStatus("fail");
        setLlmTestMsg("LLM 返回为空");
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
