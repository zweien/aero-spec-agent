import assert from "node:assert/strict";
import test from "node:test";

// llmSettings reads/writes localStorage at call time and guards reads with
// `typeof window === "undefined"` (SSR). Stub BOTH for node.
const store = new Map<string, string>();
(globalThis as Record<string, unknown>).localStorage = {
  getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
  setItem: (k: string, v: string) => void store.set(k, v),
  removeItem: (k: string) => void store.delete(k),
};
(globalThis as Record<string, unknown>).window = {
  dispatchEvent: () => true,
};

const {
  getLlmSettings,
  getProfiles,
  getActiveProfileId,
  setActiveProfileId,
  addProfile,
  removeProfile,
  updateProfile,
} = await import("./llmSettings.ts");

function reset(): void {
  store.clear();
}

test("no profiles and no selection → empty settings (server default)", () => {
  reset();
  const s = getLlmSettings();
  assert.deepEqual(s, { modelName: "", apiKey: "", baseUrl: "" });
});

test("active profile is returned", () => {
  reset();
  const a = addProfile("A", { modelName: "model-a", apiKey: "key-a", baseUrl: "http://a/v1" });
  addProfile("B", { modelName: "model-b", apiKey: "key-b", baseUrl: "http://b/v1" });
  setActiveProfileId(a.id);
  const s = getLlmSettings();
  assert.equal(s.modelName, "model-a");
});

test("regression: profiles exist but none selected → server default, NOT profiles[0]", () => {
  // The old getLlmSettings fell back to profiles[0] when activeId was empty,
  // which made the "（默认）" option a no-op — the "cannot switch models" bug.
  reset();
  addProfile("A", { modelName: "model-a", apiKey: "key-a", baseUrl: "http://a/v1" });
  setActiveProfileId(""); // user picked "server default"
  const s = getLlmSettings();
  assert.deepEqual(s, { modelName: "", apiKey: "", baseUrl: "" });
});

test("regression: active id points at a deleted profile → server default", () => {
  reset();
  const a = addProfile("A", { modelName: "model-a", apiKey: "key-a", baseUrl: "http://a/v1" });
  addProfile("B", { modelName: "model-b", apiKey: "key-b", baseUrl: "http://b/v1" });
  setActiveProfileId(a.id);
  removeProfile(a.id);
  const s = getLlmSettings();
  assert.deepEqual(s, { modelName: "", apiKey: "", baseUrl: "" });
});

test("updateProfile persists edits to the right profile", () => {
  reset();
  const a = addProfile("A", { modelName: "old", apiKey: "k", baseUrl: "http://a/v1" });
  updateProfile(a.id, { modelName: "new" });
  const profiles = getProfiles();
  assert.equal(profiles.find((p) => p.id === a.id)?.modelName, "new");
});

test("removing the active profile clears the active id", () => {
  reset();
  const a = addProfile("A", { modelName: "m", apiKey: "k", baseUrl: "http://a/v1" });
  removeProfile(a.id);
  const active = getActiveProfileId();
  assert.ok(!active, `expected empty active id, got ${JSON.stringify(active)}`);
});
