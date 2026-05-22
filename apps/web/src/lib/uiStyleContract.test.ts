import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function source(path: string): string {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("root layout exposes Inter and globals use DESIGN tokens", () => {
  const layout = source("app/layout.tsx");
  const css = source("app/globals.css");
  const baseFieldRule = css.match(/input:not\(\[type\]\),[\s\S]*?select \{[\s\S]*?\n}/)?.[0];

  assert.match(layout, /import \{ Inter \} from "next\/font\/google"/);
  assert.match(layout, /variable: "--font-inter"/);
  assert.match(layout, /className=\{inter\.variable\}/);

  assert.match(css, /--bg-base:\s*#08090a;/);
  assert.match(css, /--accent:\s*#7170ff;/);
  assert.match(css, /--font:\s*var\(--font-inter\)/);
  assert.doesNotMatch(css, /Outfit/);
  assert.doesNotMatch(css, /#06b6d4|#22d3ee/);
  assert.doesNotMatch(css, /input:not\(\[type="checkbox"\]\)/);
  assert.ok(baseFieldRule);
  assert.doesNotMatch(baseFieldRule, /outline:\s*none;/);
});

test("workspace settings and metrics use semantic UI classes", () => {
  const page = source("app/page.tsx");
  const settings = source("components/settings-panel/SettingsPanel.tsx");
  const metrics = source("components/metrics/DesignMetricsCard.tsx");

  assert.match(page, /className=\{`topbar-compare/);
  assert.doesNotMatch(page, /background: compareState\.items\.length/);

  assert.match(settings, /settings-profile-row/);
  assert.match(settings, /settings-preset/);
  assert.doesNotMatch(settings, /style=\{\{/);

  assert.match(metrics, /design-metrics-card/);
  assert.match(metrics, /risk-level-\$\{riskLevel\}/);
  assert.doesNotMatch(metrics, /style=\{\{/);
});
