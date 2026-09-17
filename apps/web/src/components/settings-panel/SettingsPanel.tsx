"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
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
  /** Notified after a successful settings save so the page can react to a
   *  CAD backend switch (e.g. toggling wireframe stand-in behaviour). */
  onSettingsSaved?: (settings: { cad_backend: string; run_vspaero_analysis: boolean }) => void;
};

/** Which profile card has its editor expanded (null = none). */
type Draft = { name: string; modelName: string; apiKey: string; baseUrl: string };

type Creating =
  | { step: "preset" }
  | { step: "name"; template: (typeof PRESET_TEMPLATES)[number] };

const EMPTY_DRAFT: Draft = { name: "", modelName: "", apiKey: "", baseUrl: "" };

function draftFromProfile(p: LlmProfile): Draft {
  return { name: p.name, modelName: p.modelName, apiKey: p.apiKey, baseUrl: p.baseUrl };
}

export function SettingsPanel({ apiBaseUrl, onSettingsSaved }: SettingsPanelProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  // --- CAD generation settings ---
  const [backend, setBackend] = useState<string>("fake");
  const [vspaero, setVspaero] = useState(false);
  const [loading, setLoading] = useState(false);

  // --- LLM profiles ---
  const [profiles, setProfiles] = useState<LlmProfile[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [showKey, setShowKey] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [creating, setCreating] = useState<Creating | null>(null);
  const [newName, setNewName] = useState("");
  const [llmTestStatus, setLlmTestStatus] = useState<LlmTestStatus>("idle");
  const [llmTestMsg, setLlmTestMsg] = useState("");

  const flushDraft = useCallback(() => {
    if (expandedId && draft.name.trim()) {
      updateProfile(expandedId, {
        name: draft.name.trim(),
        modelName: draft.modelName.trim(),
        apiKey: draft.apiKey.trim(),
        baseUrl: draft.baseUrl.trim(),
      });
      setProfiles(getProfiles());
    }
  }, [expandedId, draft]);

  const openEditor = useCallback((p: LlmProfile) => {
    flushDraft(); // persist edits in the previously expanded card first
    setExpandedId(p.id);
    setDraft(draftFromProfile(p));
    setLlmTestStatus("idle");
    setLlmTestMsg("");
    setShowKey(false);
    setDeletingId(null);
  }, [flushDraft]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        flushDraft();
        setOpen(false);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, flushDraft]);

  // Open on request from elsewhere (e.g. the chat input's model indicator)
  useEffect(() => {
    const onOpen = () => setOpen(true);
    window.addEventListener("aerospec-open-settings", onOpen);
    return () => window.removeEventListener("aerospec-open-settings", onOpen);
  }, []);

  useEffect(() => {
    if (!open) return;
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
    const p = getProfiles();
    setProfiles(p);
    const aid = getActiveProfileId() ?? "";
    setActiveId(aid);
    const active = p.find((x) => x.id === aid);
    if (active) {
      setExpandedId(active.id);
      setDraft(draftFromProfile(active));
    } else {
      setExpandedId(null);
      setDraft(EMPTY_DRAFT);
    }
  }, [apiBaseUrl, open]);

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
          onSettingsSaved?.(data);
        }
      } catch { /* ignore */ }
      setLoading(false);
    },
    [apiBaseUrl, onSettingsSaved],
  );

  const handleFieldBlur = useCallback(() => {
    flushDraft();
    setSavedFlash(true);
    window.setTimeout(() => setSavedFlash(false), 1200);
  }, [flushDraft]);

  const activate = useCallback((id: string) => {
    flushDraft();
    setActiveProfileId(id);
    setActiveId(id);
    if (!id) {
      setExpandedId(null);
      setDraft(EMPTY_DRAFT);
    }
  }, [flushDraft]);

  const handleDelete = useCallback((id: string) => {
    removeProfile(id);
    const updated = getProfiles();
    setProfiles(updated);
    setDeletingId(null);
    if (activeId === id) {
      // Removing the active profile falls back to the server default.
      setActiveProfileId("");
      setActiveId("");
      setExpandedId(null);
      setDraft(EMPTY_DRAFT);
    }
    if (expandedId === id) {
      setExpandedId(null);
      setDraft(EMPTY_DRAFT);
    }
  }, [activeId, expandedId]);

  const handleCreate = useCallback(() => {
    if (creating?.step !== "name" || !newName.trim()) return;
    const t = creating.template;
    const p = addProfile(newName.trim(), {
      modelName: t.modelName,
      apiKey: "",
      baseUrl: t.baseUrl,
    });
    setProfiles(getProfiles());
    setActiveId(p.id);
    setExpandedId(p.id);
    setDraft({ name: p.name, modelName: p.modelName, apiKey: "", baseUrl: p.baseUrl });
    setCreating(null);
    setNewName("");
  }, [creating, newName]);

  const testLlm = useCallback(async () => {
    if (!draft.apiKey && !draft.baseUrl) {
      setLlmTestStatus("fail");
      setLlmTestMsg("请先填写 API Key 或 Base URL");
      return;
    }
    flushDraft();
    setLlmTestStatus("testing");
    setLlmTestMsg("");
    try {
      const resp = await fetch("/api/llm-test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          modelName: draft.modelName || undefined,
          apiKey: draft.apiKey || undefined,
          baseUrl: draft.baseUrl || undefined,
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
  }, [draft, flushDraft]);

  const closeDrawer = useCallback(() => {
    flushDraft();
    setOpen(false);
  }, [flushDraft]);

  return (
    <div className="settings-panel" ref={rootRef}>
      <button
        type="button"
        className="settings-toggle"
        onClick={() => setOpen(!open)}
      >
        设置
      </button>
      {open && (
        <>
          <div className="settings-drawer-mask" onClick={closeDrawer} />
          <div className="settings-drawer" role="dialog" aria-label="设置">
            <div className="settings-drawer-header">
              <strong>设置</strong>
              <button
                type="button"
                className="settings-drawer-close"
                onClick={closeDrawer}
                aria-label="关闭设置"
              >
                ×
              </button>
            </div>

            <div className="settings-drawer-body">
              {/* ---------- 模型配置 ---------- */}
              <div className="settings-section-title">模型配置</div>

              {/* Server default card */}
              <div
                className={`llm-card${activeId === "" ? " llm-card-active" : ""}`}
                onClick={() => activate("")}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === "Enter") activate(""); }}
              >
                <div className="llm-card-main">
                  <span className="llm-card-name">服务器默认</span>
                  <span className="llm-card-meta">使用服务器端 .env 配置的模型</span>
                </div>
                {activeId === "" && <span className="llm-card-badge">使用中</span>}
              </div>

              {/* Profile cards */}
              {profiles.map((p) => {
                const isActive = p.id === activeId;
                const isExpanded = p.id === expandedId;
                return (
                  <div
                    key={p.id}
                    className={`llm-card${isActive ? " llm-card-active" : ""}${isExpanded ? " llm-card-expanded" : ""}`}
                    onClick={() => {
                      if (isActive && isExpanded) {
                        // collapse: flush edits first
                        flushDraft();
                        setExpandedId(null);
                      } else {
                        activate(p.id);
                        openEditor(p);
                      }
                    }}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => { if (e.key === "Enter") activate(p.id); }}
                  >
                    <div className="llm-card-row">
                      <div className="llm-card-main">
                        <span className="llm-card-name">{p.name}</span>
                        <span className="llm-card-meta">
                          {p.modelName || "（未设置模型）"}
                          {p.baseUrl ? ` · ${p.baseUrl.replace(/^https?:\/\//, "")}` : ""}
                        </span>
                      </div>
                      {isActive && <span className="llm-card-badge">使用中</span>}
                    </div>

                    {isExpanded && (
                      <div className="llm-card-editor" onClick={(e) => e.stopPropagation()}>
                        <label className="settings-row">
                          <span className="settings-label">配置名称</span>
                          <input
                            type="text"
                            value={draft.name}
                            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                            onBlur={handleFieldBlur}
                            className="settings-inline-field"
                          />
                        </label>
                        <label className="settings-row">
                          <span className="settings-label">模型</span>
                          <input
                            type="text"
                            value={draft.modelName}
                            onChange={(e) => setDraft({ ...draft, modelName: e.target.value })}
                            onBlur={handleFieldBlur}
                            placeholder="如 deepseek-chat"
                            className="settings-inline-field"
                          />
                        </label>
                        <label className="settings-row">
                          <span className="settings-label">API Key</span>
                          <span className="settings-key-field">
                            <input
                              type={showKey ? "text" : "password"}
                              value={draft.apiKey}
                              onChange={(e) => setDraft({ ...draft, apiKey: e.target.value })}
                              onBlur={handleFieldBlur}
                              placeholder="sk-…"
                              className="settings-inline-field"
                              autoComplete="off"
                            />
                            <button
                              type="button"
                              className="settings-key-toggle"
                              onClick={() => setShowKey(!showKey)}
                              aria-label={showKey ? "隐藏 API Key" : "显示 API Key"}
                              title={showKey ? "隐藏" : "显示"}
                            >
                              {showKey ? "隐藏" : "显示"}
                            </button>
                          </span>
                        </label>
                        <label className="settings-row">
                          <span className="settings-label">Base URL</span>
                          <input
                            type="text"
                            value={draft.baseUrl}
                            onChange={(e) => setDraft({ ...draft, baseUrl: e.target.value })}
                            onBlur={handleFieldBlur}
                            placeholder="https://api.openai.com/v1"
                            className="settings-inline-field"
                          />
                        </label>

                        <div className="settings-actions-row">
                          {savedFlash && <span className="llm-saved-flash">已保存</span>}
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

                        {deletingId === p.id ? (
                          <div className="llm-delete-confirm">
                            <span>删除配置「{p.name}」？</span>
                            <button type="button" className="llm-delete-yes" onClick={() => handleDelete(p.id)}>删除</button>
                            <button type="button" className="llm-delete-no" onClick={() => setDeletingId(null)}>取消</button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            className="llm-delete-btn"
                            onClick={() => setDeletingId(p.id)}
                          >
                            删除此配置
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}

              {/* New profile flow */}
              {creating?.step === "preset" ? (
                <div className="llm-create-box">
                  <div className="llm-create-title">选择预设</div>
                  <div className="llm-preset-grid">
                    {PRESET_TEMPLATES.map((t) => (
                      <button
                        key={t.name}
                        type="button"
                        className="llm-preset-btn"
                        onClick={() => { setCreating({ step: "name", template: t }); setNewName(t.name === "自定义" ? "" : t.name); }}
                      >
                        <span className="llm-preset-name">{t.name}</span>
                        {t.modelName && <span className="llm-preset-model">{t.modelName}</span>}
                      </button>
                    ))}
                  </div>
                  <button type="button" className="llm-create-cancel" onClick={() => setCreating(null)}>取消</button>
                </div>
              ) : creating?.step === "name" ? (
                <div className="llm-create-box">
                  <div className="llm-create-title">配置名称</div>
                  <input
                    type="text"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") handleCreate(); }}
                    placeholder="如 我的 DeepSeek"
                    className="settings-field-input"
                    autoFocus
                  />
                  <div className="llm-create-actions">
                    <button type="button" className="llm-test-btn" disabled={!newName.trim()} onClick={handleCreate}>创建</button>
                    <button type="button" className="llm-create-cancel" onClick={() => setCreating(null)}>取消</button>
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  className="llm-card llm-card-new"
                  onClick={() => setCreating({ step: "preset" })}
                >
                  + 新建配置
                </button>
              )}

              {/* ---------- CAD 生成 ---------- */}
              <div className="settings-section-title settings-section-spaced">CAD 生成</div>
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
                <span className="settings-label">气动分析（VSPAERO）</span>
                <input
                  type="checkbox"
                  checked={vspaero}
                  disabled={loading}
                  onChange={(e) => void save({ run_vspaero_analysis: e.target.checked })}
                />
              </label>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
