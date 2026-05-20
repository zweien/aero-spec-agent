"use client";

export type LlmSettings = {
  modelName: string;
  apiKey: string;
  baseUrl: string;
};

const LLM_SETTINGS_KEY = "aerospec-llm-settings";

const DEFAULTS: LlmSettings = {
  modelName: "",
  apiKey: "",
  baseUrl: "",
};

export function getLlmSettings(): LlmSettings {
  if (typeof window === "undefined") return { ...DEFAULTS };
  try {
    const raw = localStorage.getItem(LLM_SETTINGS_KEY);
    if (!raw) return { ...DEFAULTS };
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveLlmSettings(patch: Partial<LlmSettings>): void {
  const current = getLlmSettings();
  const updated = { ...current, ...patch };
  localStorage.setItem(LLM_SETTINGS_KEY, JSON.stringify(updated));
}
