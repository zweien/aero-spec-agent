"use client";

export type LlmSettings = {
  modelName: string;
  apiKey: string;
  baseUrl: string;
};

export type LlmProfile = {
  id: string;
  name: string;
  modelName: string;
  apiKey: string;
  baseUrl: string;
};

const OLD_KEY = "aerospec-llm-settings";
const PROFILES_KEY = "aerospec-llm-profiles";
const ACTIVE_KEY = "aerospec-llm-active-id";

const DEFAULTS: LlmSettings = {
  modelName: "",
  apiKey: "",
  baseUrl: "",
};

// --- Change notification (for the chat input's current-model indicator) ---

export const LLM_SETTINGS_CHANGED_EVENT = "aerospec-llm-settings-changed";

function notifyChanged(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(LLM_SETTINGS_CHANGED_EVENT));
}

// --- Active settings resolution ---

/**
 * Resolve the settings for the NEXT chat request.
 *
 * - No profile selected (or the selected id no longer exists) → empty
 *   settings = "server default": the request goes through the legacy
 *   FastAPI path using the backend's OPENAI_* env config.
 * - A profile is selected → that profile's model/key/baseUrl.
 *
 * Note: this used to fall back to profiles[0] when nothing was selected,
 * which made the "（默认）" option a no-op as soon as any profile existed —
 * the "cannot switch models" bug.
 */
export function getLlmSettings(): LlmSettings {
  if (typeof window === "undefined") return { ...DEFAULTS };
  const profiles = getProfiles();
  const activeId = getActiveProfileId();
  if (activeId) {
    const p = profiles.find((p) => p.id === activeId);
    if (p) return { modelName: p.modelName, apiKey: p.apiKey, baseUrl: p.baseUrl };
  }
  // Server default: legacy single-settings only mattered pre-profiles; when
  // profiles exist but none is active, the server default is the honest answer.
  return { ...DEFAULTS };
}

export function saveLlmSettings(patch: Partial<LlmSettings>): void {
  const current = getLlmSettings();
  const updated = { ...current, ...patch };
  localStorage.setItem(OLD_KEY, JSON.stringify(updated));
  notifyChanged();
}

// --- Multi-profile management ---

export function getProfiles(): LlmProfile[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(PROFILES_KEY);
    if (!raw) {
      // Migrate from old single-settings
      return migrateFromOld();
    }
    return JSON.parse(raw) as LlmProfile[];
  } catch {
    return [];
  }
}

export function saveProfiles(profiles: LlmProfile[]): void {
  localStorage.setItem(PROFILES_KEY, JSON.stringify(profiles));
  notifyChanged();
}

export function getActiveProfileId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACTIVE_KEY);
}

export function setActiveProfileId(id: string): void {
  localStorage.setItem(ACTIVE_KEY, id);
  notifyChanged();
}

export function addProfile(name: string, settings: LlmSettings): LlmProfile {
  const profiles = getProfiles();
  const profile: LlmProfile = {
    id: crypto.randomUUID(),
    name,
    ...settings,
  };
  profiles.push(profile);
  saveProfiles(profiles);
  setActiveProfileId(profile.id);
  return profile;
}

export function removeProfile(id: string): void {
  const profiles = getProfiles().filter((p) => p.id !== id);
  saveProfiles(profiles);
  const activeId = getActiveProfileId();
  if (activeId === id) {
    // Removing the active profile falls back to the SERVER DEFAULT — never
    // silently jump to another profile (that was part of the "switching
    // models doesn't work" confusion). The user picks the next one.
    setActiveProfileId("");
  }
}

export function updateProfile(id: string, patch: Partial<Omit<LlmProfile, "id">>): void {
  const profiles = getProfiles().map((p) =>
    p.id === id ? { ...p, ...patch } : p,
  );
  saveProfiles(profiles);
}

/** Predefined quick-fill templates */
export const PRESET_TEMPLATES: Array<{ name: string; modelName: string; baseUrl: string }> = [
  { name: "DeepSeek", modelName: "deepseek-chat", baseUrl: "https://api.deepseek.com/v1" },
  { name: "OpenAI", modelName: "gpt-4o", baseUrl: "https://api.openai.com/v1" },
  { name: "MiniMax-M2.5", modelName: "MiniMax-M2.5", baseUrl: "http://192.168.2.220:3000/v1" },
  { name: "自定义", modelName: "", baseUrl: "" },
];

function migrateFromOld(): LlmProfile[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(OLD_KEY);
    if (!raw) return [];
    const old = JSON.parse(raw) as LlmSettings;
    if (!old.modelName && !old.apiKey && !old.baseUrl) return [];
    const profile: LlmProfile = {
      id: crypto.randomUUID(),
      name: "默认",
      ...old,
    };
    saveProfiles([profile]);
    setActiveProfileId(profile.id);
    return [profile];
  } catch {
    return [];
  }
}
