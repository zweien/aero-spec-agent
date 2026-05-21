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

// --- Legacy single-settings (backward compat) ---

export function getLlmSettings(): LlmSettings {
  // Try active profile first
  const profiles = getProfiles();
  const activeId = getActiveProfileId();
  if (profiles.length > 0 && activeId) {
    const p = profiles.find((p) => p.id === activeId);
    if (p) return { modelName: p.modelName, apiKey: p.apiKey, baseUrl: p.baseUrl };
  }
  if (profiles.length > 0) {
    const p = profiles[0];
    return { modelName: p.modelName, apiKey: p.apiKey, baseUrl: p.baseUrl };
  }
  // Fallback to old format
  if (typeof window === "undefined") return { ...DEFAULTS };
  try {
    const raw = localStorage.getItem(OLD_KEY);
    if (!raw) return { ...DEFAULTS };
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveLlmSettings(patch: Partial<LlmSettings>): void {
  const current = getLlmSettings();
  const updated = { ...current, ...patch };
  localStorage.setItem(OLD_KEY, JSON.stringify(updated));
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
}

export function getActiveProfileId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACTIVE_KEY);
}

export function setActiveProfileId(id: string): void {
  localStorage.setItem(ACTIVE_KEY, id);
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
    setActiveProfileId(profiles.length > 0 ? profiles[0].id : "");
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
