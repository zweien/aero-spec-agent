# DESIGN.md UI Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify every `apps/web` UI surface with the dark workbench visual language defined in the root `DESIGN.md`.

**Architecture:** Keep the current Next.js single-page workspace and use `globals.css` as the styling center. Establish typography, tokens, base controls, and a source-level style contract first; then replace inline and hard-coded styling in feature groups with semantic class names while preserving business state and layout flow.

**Tech Stack:** Next.js 14 App Router, React 18, TypeScript, global CSS, `next/font`, Node test runner with `--experimental-strip-types`, browser QA.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `apps/web/src/app/layout.tsx` | Load Inter through `next/font` and expose the font variable to the global style layer. |
| `apps/web/src/app/globals.css` | Hold design tokens, base controls, shared UI semantics, workspace layout, and feature-area CSS. |
| `apps/web/src/app/page.tsx` | Replace topbar Compare control inline styling with semantic classes while preserving split-width state. |
| `apps/web/src/lib/uiStyleContract.test.ts` | Guard typography, token, class, and hard-coded-style cleanup contracts from source files. |
| `apps/web/src/components/settings-panel/SettingsPanel.tsx` | Move settings form and compact action styling from inline objects to shared classes. |
| `apps/web/src/components/metrics/DesignMetricsCard.tsx` | Move metric-card layout and semantic risk styling into CSS classes. |
| `apps/web/src/components/compare/*.tsx` | Convert Compare drawer, cards, table, cells, and add-to-compare action to shared UI semantics. |
| `apps/web/src/components/graph/*.tsx` | Convert Deep Design controls, recommendations, variant cards, and thumbnails to semantic graph classes. |
| `apps/web/src/components/chat/*.tsx` | Align notices, agent run status, detail rows, and workflow timeline states. |
| `apps/web/src/components/runtime/*.tsx` | Align defaulted fields, runtime task progress, workflow error, and unified timeline states. |
| `apps/web/src/components/cad-viewer/CADLoadingOverlay.tsx` | Replace overlay inline color treatments with CAD state classes. |
| `apps/web/src/components/version-panel/VersionPanel.tsx` | Remove small local style forks from version and rule surfaces. |

## Task 1: Add UI Style Contract And Token Foundation

**Files:**
- Create: `apps/web/src/lib/uiStyleContract.test.ts`
- Modify: `apps/web/src/app/layout.tsx`
- Modify: `apps/web/src/app/globals.css`

- [ ] **Step 1: Write the failing typography and token contract**

Create `apps/web/src/lib/uiStyleContract.test.ts` with the first contract:

```ts
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function source(path: string): string {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("root layout exposes Inter and globals use DESIGN tokens", () => {
  const layout = source("app/layout.tsx");
  const css = source("app/globals.css");

  assert.match(layout, /import \{ Inter \} from "next\/font\/google"/);
  assert.match(layout, /variable: "--font-inter"/);
  assert.match(layout, /className=\{inter\.variable\}/);

  assert.match(css, /--bg-base:\s*#08090a;/);
  assert.match(css, /--accent:\s*#7170ff;/);
  assert.match(css, /--font:\s*var\(--font-inter\)/);
  assert.doesNotMatch(css, /Outfit/);
  assert.doesNotMatch(css, /#06b6d4|#22d3ee/);
});
```

- [ ] **Step 2: Run the new contract and verify it fails**

Run:

```bash
cd "apps/web" && node --test --experimental-strip-types --test-name-pattern "root layout exposes Inter" "src/lib/uiStyleContract.test.ts"
```

Expected: FAIL because `layout.tsx` does not load `Inter`, `globals.css` still imports Outfit, and the old cyan tokens remain.

- [ ] **Step 3: Load Inter in the root layout**

Update `apps/web/src/app/layout.tsx` to initialize the variable font and keep the existing metadata:

```tsx
import "./globals.css";
import type { Metadata } from "next";
import { Inter } from "next/font/google";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "AeroSpec Agent",
  description: "Aircraft concept design workbench",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className={inter.variable}>
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 4: Replace the token and base-control foundation**

Replace the Outfit import and `:root` token block at the top of `apps/web/src/app/globals.css` with a `DESIGN.md` workbench token set:

```css
:root {
  --bg-base: #08090a;
  --bg-panel: #0f1011;
  --bg-elevated: #141516;
  --bg-surface: rgba(255, 255, 255, 0.04);
  --bg-hover: rgba(255, 255, 255, 0.07);
  --bg-overlay: rgba(0, 0, 0, 0.85);
  --border: rgba(255, 255, 255, 0.05);
  --border-default: rgba(255, 255, 255, 0.08);
  --border-strong: rgba(255, 255, 255, 0.14);
  --text: #f7f8f8;
  --text-dim: #d0d6e0;
  --text-muted: #8a8f98;
  --text-subtle: #62666d;
  --accent: #7170ff;
  --accent-bright: #828fff;
  --accent-solid: #5e6ad2;
  --accent-bg: rgba(113, 112, 255, 0.14);
  --accent-border: rgba(130, 143, 255, 0.32);
  --success: #27a644;
  --success-bg: rgba(39, 166, 68, 0.12);
  --success-border: rgba(39, 166, 68, 0.28);
  --warning: #f3c969;
  --warning-bg: rgba(243, 201, 105, 0.12);
  --warning-border: rgba(243, 201, 105, 0.24);
  --error: #f97068;
  --error-bg: rgba(249, 112, 104, 0.12);
  --error-border: rgba(249, 112, 104, 0.24);
  --info-bg: rgba(113, 112, 255, 0.1);
  --info-border: rgba(130, 143, 255, 0.24);
  --user-bg: rgba(94, 106, 210, 0.2);
  --shadow-panel: 0 16px 48px rgba(0, 0, 0, 0.32);
  --shadow-soft: 0 0 0 1px rgba(255, 255, 255, 0.03), 0 12px 32px rgba(0, 0, 0, 0.24);
  --radius: 8px;
  --radius-sm: 6px;
  --font: var(--font-inter), "Inter Variable", "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: "Berkeley Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
```

Then update the reset and base controls so typography and keyboard focus are shared:

```css
html, body {
  height: 100%;
  margin: 0;
  background: var(--bg-base);
  color: var(--text);
  font-family: var(--font);
  font-feature-settings: "cv01", "ss03";
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

:focus-visible {
  outline: 2px solid var(--accent-bright);
  outline-offset: 2px;
}

button {
  min-height: 38px;
  padding: 0 14px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text);
  cursor: pointer;
  font-weight: 510;
  font-size: 13px;
  transition: background 0.12s, border-color 0.12s, color 0.12s, transform 0.12s;
}

button:hover:not(:disabled) {
  background: var(--bg-hover);
  border-color: var(--border-strong);
}

button:disabled {
  background: rgba(255, 255, 255, 0.02);
  color: var(--text-subtle);
  cursor: not-allowed;
}

input, textarea, select {
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.02);
  color: var(--text);
}
```

- [ ] **Step 5: Run the token contract and frontend build**

Run:

```bash
cd "apps/web" && node --test --experimental-strip-types --test-name-pattern "root layout exposes Inter" "src/lib/uiStyleContract.test.ts"
cd "apps/web" && npm run build
```

Expected: the new contract passes and Next.js build succeeds.

- [ ] **Step 6: Commit**

```bash
git add "apps/web/src/lib/uiStyleContract.test.ts" "apps/web/src/app/layout.tsx" "apps/web/src/app/globals.css"
git commit -m "style: establish design md ui tokens"
```

## Task 2: Unify Workspace Shell, Settings, And Metrics

**Files:**
- Modify: `apps/web/src/lib/uiStyleContract.test.ts`
- Modify: `apps/web/src/app/page.tsx`
- Modify: `apps/web/src/app/globals.css`
- Modify: `apps/web/src/components/settings-panel/SettingsPanel.tsx`
- Modify: `apps/web/src/components/metrics/DesignMetricsCard.tsx`

- [ ] **Step 1: Add failing class contracts for shell, settings, and metrics**

Append to `apps/web/src/lib/uiStyleContract.test.ts`:

```ts
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
```

- [ ] **Step 2: Run the contract and verify it fails**

Run:

```bash
cd "apps/web" && node --test --experimental-strip-types --test-name-pattern "workspace settings and metrics" "src/lib/uiStyleContract.test.ts"
```

Expected: FAIL because the shell Compare button, Settings rows, and metrics card still use inline style objects.

- [ ] **Step 3: Move shell, Settings, and metric surfaces to semantic classes**

Keep the dynamic chat-column width inline because it is live resize state. Replace the topbar Compare style object in `page.tsx` with:

```tsx
<button
  onClick={() => setCompareDrawerOpen(true)}
  className={`topbar-compare ${compareState.items.length > 0 ? "topbar-compare-active" : ""}`}
>
  方案对比{compareState.items.length > 0 ? ` (${compareState.items.length})` : ""}
</button>
```

Use semantic class names in `SettingsPanel.tsx`, for example:

```tsx
<div className="settings-section-title settings-section-spaced">LLM 配置</div>
<div className="settings-row settings-profile-row">
  <select className="settings-profile-select" value={activeId} onChange={(e) => handleSelectProfile(e.target.value)}>
    ...
  </select>
  <button type="button" className="toolbar-button" onClick={() => setShowAddForm(!showAddForm)} title="添加配置">+</button>
</div>
<button key={t.name} type="button" className="settings-preset" onClick={() => handlePreset(t)}>
  {t.name}
</button>
```

Refactor `DesignMetricsCard.tsx` to keep the dynamic risk level in the class name instead of a style function:

```tsx
<div className="design-metrics-card">
  {versionLabel && <div className="design-metrics-title">{versionLabel} 设计指标</div>}
  <div className="design-metrics-grid">
    {displays.map((d) => (
      <div key={d.key} className="design-metrics-row">
        <span className="design-metrics-label">{d.label}</span>
        <span className="design-metrics-value">{d.value}{d.unit ? ` ${d.unit}` : ""}</span>
      </div>
    ))}
  </div>
  <div className="design-metrics-meta">
    <span>风险等级: <span className={`risk-level risk-level-${riskLevel}`}>{riskLabel(riskLevel)}</span></span>
    <span>置信度: <span className="design-metrics-confidence">{CONFIDENCE_LABELS[confidence]}</span></span>
  </div>
</div>
```

Add the shared CSS roles in `globals.css`:

```css
.button-primary,
.chat-input-row button,
.apply-changes-pending {
  background: var(--accent-solid);
  border-color: var(--accent-border);
  color: #fff;
}

.toolbar-button {
  min-height: 24px;
  padding: 0 7px;
  font-size: 11px;
}

.topbar-compare,
.settings-preset {
  background: transparent;
  color: var(--text-dim);
}

.topbar-compare-active {
  background: var(--accent-bg);
  border-color: var(--accent-border);
  color: var(--accent-bright);
}

.design-metrics-card {
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  padding: 12px;
  background: var(--bg-surface);
  box-shadow: var(--shadow-soft);
  font-size: 12px;
}
```

- [ ] **Step 4: Run the targeted contract and full frontend tests**

Run:

```bash
cd "apps/web" && node --test --experimental-strip-types --test-name-pattern "workspace settings and metrics" "src/lib/uiStyleContract.test.ts"
cd "apps/web" && npm test
```

Expected: targeted contract and frontend test suite pass.

- [ ] **Step 5: Commit**

```bash
git add "apps/web/src/lib/uiStyleContract.test.ts" "apps/web/src/app/page.tsx" "apps/web/src/app/globals.css" "apps/web/src/components/settings-panel/SettingsPanel.tsx" "apps/web/src/components/metrics/DesignMetricsCard.tsx"
git commit -m "style: unify workspace control surfaces"
```

## Task 3: Convert Compare View To Shared UI Semantics

**Files:**
- Modify: `apps/web/src/lib/uiStyleContract.test.ts`
- Modify: `apps/web/src/app/globals.css`
- Modify: `apps/web/src/components/compare/AddToCompareButton.tsx`
- Modify: `apps/web/src/components/compare/CompareDrawer.tsx`
- Modify: `apps/web/src/components/compare/CompareItemCard.tsx`
- Modify: `apps/web/src/components/compare/CompareMetricCell.tsx`
- Modify: `apps/web/src/components/compare/CompareTable.tsx`

- [ ] **Step 1: Add failing Compare source contracts**

Append to `apps/web/src/lib/uiStyleContract.test.ts`:

```ts
test("compare view uses drawer and table class semantics", () => {
  const drawer = source("components/compare/CompareDrawer.tsx");
  const table = source("components/compare/CompareTable.tsx");
  const card = source("components/compare/CompareItemCard.tsx");

  assert.match(drawer, /compare-drawer/);
  assert.match(drawer, /notice notice-info/);
  assert.match(table, /compare-table-scroll/);
  assert.match(card, /compare-item-card/);
  assert.doesNotMatch(drawer, /style=\{\{/);
  assert.doesNotMatch(table, /style=\{\{/);
  assert.doesNotMatch(card, /style=\{\{/);
});
```

- [ ] **Step 2: Run the Compare contract and verify it fails**

Run:

```bash
cd "apps/web" && node --test --experimental-strip-types --test-name-pattern "compare view uses drawer" "src/lib/uiStyleContract.test.ts"
```

Expected: FAIL because Compare components are still almost entirely inline-styled.

- [ ] **Step 3: Refactor Compare markup to semantic classes**

Use classes for the drawer shell, notices, card row, cards, metrics, and tables. The drawer content should read like:

```tsx
<div className="compare-drawer">
  <div className="compare-drawer-header">
    <div className="compare-drawer-title-row">
      <span className="compare-drawer-title">方案对比</span>
      <span className="pill pill-neutral">{items.length} 个方案</span>
    </div>
    <div className="compare-drawer-actions">
      <button className="toolbar-button" onClick={handleExport} disabled={!hasMinItems}>导出对比报告</button>
      {items.length > 0 && <button className="toolbar-button" onClick={onClear}>清空对比</button>}
      <button className="icon-button" onClick={onClose} aria-label="关闭方案对比">&times;</button>
    </div>
  </div>
  <div className="compare-drawer-body">...</div>
</div>
```

Use `notice notice-info`, `notice notice-warning`, `compare-item-row`, `compare-item-slot`, `compare-table-scroll`, `compare-table`, `compare-metric-value`, and `compare-empty-state` instead of inline style objects.

- [ ] **Step 4: Add Compare CSS in the feature section**

Add feature classes beside the existing Compare CSS in `globals.css`:

```css
.compare-drawer {
  position: fixed;
  inset: 0 0 0 auto;
  z-index: 1000;
  width: min(960px, 94vw);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-left: 1px solid var(--border-default);
  background: var(--bg-panel);
  box-shadow: var(--shadow-panel);
}

.notice {
  padding: 8px 12px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  font-size: 11px;
  line-height: 1.5;
}

.notice-info {
  border-color: var(--info-border);
  background: var(--info-bg);
  color: var(--text-dim);
}

.notice-warning {
  border-color: var(--warning-border);
  background: var(--warning-bg);
  color: var(--warning);
}
```

- [ ] **Step 5: Run Compare tests and the full frontend suite**

Run:

```bash
cd "apps/web" && node --test --experimental-strip-types --test-name-pattern "compare view uses drawer" "src/lib/uiStyleContract.test.ts"
cd "apps/web" && npm test
```

Expected: Compare contract and existing frontend tests pass.

- [ ] **Step 6: Commit**

```bash
git add "apps/web/src/lib/uiStyleContract.test.ts" "apps/web/src/app/globals.css" "apps/web/src/components/compare"
git commit -m "style: align compare view with design tokens"
```

## Task 4: Convert Deep Design And Graph Cards

**Files:**
- Modify: `apps/web/src/lib/uiStyleContract.test.ts`
- Modify: `apps/web/src/app/globals.css`
- Modify: `apps/web/src/components/graph/DeepDesignPanel.tsx`
- Modify: `apps/web/src/components/graph/GraphExecutionPanel.tsx`
- Modify: `apps/web/src/components/graph/RecommendedVariantCard.tsx`
- Modify: `apps/web/src/components/graph/VariantSummaryCard.tsx`
- Modify: `apps/web/src/components/graph/VariantThumbnail.tsx`

- [ ] **Step 1: Add failing graph style contracts**

Append:

```ts
test("deep design and graph cards use semantic class names", () => {
  const deepDesign = source("components/graph/DeepDesignPanel.tsx");
  const recommendation = source("components/graph/RecommendedVariantCard.tsx");
  const summary = source("components/graph/VariantSummaryCard.tsx");
  const thumbnail = source("components/graph/VariantThumbnail.tsx");

  assert.match(deepDesign, /deep-design-panel/);
  assert.match(recommendation, /recommended-variant-card/);
  assert.match(summary, /variant-summary-card/);
  assert.match(thumbnail, /variant-thumbnail/);
  assert.doesNotMatch(recommendation, /rgba\(100,120,255/);
  assert.doesNotMatch(thumbnail, /rgba\(0,180,100|rgba\(220,50,50/);
});
```

- [ ] **Step 2: Run the graph contract and verify it fails**

Run:

```bash
cd "apps/web" && node --test --experimental-strip-types --test-name-pattern "deep design and graph cards" "src/lib/uiStyleContract.test.ts"
```

Expected: FAIL because graph panel controls and recommendation surfaces still embed inline color treatments.

- [ ] **Step 3: Replace graph-local style maps with classes**

Keep dynamic width or status data in props only where required. Use class composition for status:

```tsx
<section className="panel deep-design-panel">
  <div className="deep-design-section">
    <label className="field-label">设计需求描述</label>
    <textarea className="deep-design-prompt" ... />
  </div>
</section>
```

```tsx
<article className="recommended-variant-card">
  <header className="variant-card-header">
    <span className="pill pill-accent">推荐</span>
    <span className="variant-card-title">{recommended.label}</span>
  </header>
</article>
```

```tsx
<div className={`variant-thumbnail variant-thumbnail-${variant.status}`}>
  ...
</div>
```

- [ ] **Step 4: Add graph feature classes**

Add CSS for field labels, strategy chips, graph sections, recommendation surface, trust badges, and variant thumbnail statuses:

```css
.deep-design-panel,
.deep-design-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.deep-design-section,
.recommended-variant-card,
.variant-summary-card {
  border: 1px solid var(--border-default);
  border-radius: var(--radius);
  background: var(--bg-surface);
}

.recommended-variant-card {
  border-color: var(--accent-border);
  box-shadow: 0 0 0 1px rgba(130, 143, 255, 0.08), var(--shadow-soft);
}

.variant-thumbnail-running {
  color: var(--accent-bright);
  background: var(--accent-bg);
}
```

- [ ] **Step 5: Run graph-focused tests and full tests**

Run:

```bash
cd "apps/web" && node --test --experimental-strip-types --test-name-pattern "deep design and graph cards" "src/lib/uiStyleContract.test.ts"
cd "apps/web" && npm test
```

Expected: graph contract and existing graph component tests pass.

- [ ] **Step 6: Commit**

```bash
git add "apps/web/src/lib/uiStyleContract.test.ts" "apps/web/src/app/globals.css" "apps/web/src/components/graph"
git commit -m "style: unify deep design surfaces"
```

## Task 5: Align Chat, Runtime, Version, And CAD State Surfaces

**Files:**
- Modify: `apps/web/src/lib/uiStyleContract.test.ts`
- Modify: `apps/web/src/app/globals.css`
- Modify: `apps/web/src/components/chat/AgentRunDetails.tsx`
- Modify: `apps/web/src/components/chat/AgentRunHeader.tsx`
- Modify: `apps/web/src/components/chat/FallbackToolNotice.tsx`
- Modify: `apps/web/src/components/chat/WorkflowTimeline.tsx`
- Modify: `apps/web/src/components/runtime/DefaultedFieldsNotice.tsx`
- Modify: `apps/web/src/components/runtime/TaskRuntimeCard.tsx`
- Modify: `apps/web/src/components/runtime/UnifiedWorkflowTimeline.tsx`
- Modify: `apps/web/src/components/runtime/WorkflowErrorCard.tsx`
- Modify: `apps/web/src/components/cad-viewer/CADLoadingOverlay.tsx`
- Modify: `apps/web/src/components/version-panel/VersionPanel.tsx`

- [ ] **Step 1: Add failing runtime and CAD style contracts**

Append:

```ts
test("runtime notices and cad overlays use shared state classes", () => {
  const fallbackNotice = source("components/chat/FallbackToolNotice.tsx");
  const defaultedNotice = source("components/runtime/DefaultedFieldsNotice.tsx");
  const errorCard = source("components/runtime/WorkflowErrorCard.tsx");
  const overlay = source("components/cad-viewer/CADLoadingOverlay.tsx");

  assert.match(fallbackNotice, /runtime-notice runtime-notice-info/);
  assert.match(defaultedNotice, /runtime-notice runtime-notice-info/);
  assert.match(errorCard, /workflow-error-card/);
  assert.match(overlay, /cad-loading-overlay/);
  assert.doesNotMatch(fallbackNotice, /#3b82f6|rgba\(59, 130, 246/);
  assert.doesNotMatch(defaultedNotice, /#3b82f6|rgba\(59, 130, 246/);
  assert.doesNotMatch(overlay, /#60a5fa|rgba\(96, 165, 250/);
});
```

- [ ] **Step 2: Run the runtime contract and verify it fails**

Run:

```bash
cd "apps/web" && node --test --experimental-strip-types --test-name-pattern "runtime notices and cad overlays" "src/lib/uiStyleContract.test.ts"
```

Expected: FAIL because notices and CAD overlays still embed old fallback colors and inline state styling.

- [ ] **Step 3: Convert runtime status markup**

Use shared notice, timeline, status, and progress classes:

```tsx
<div className="runtime-notice runtime-notice-info">
  <button className="runtime-notice-toggle" type="button" onClick={() => setOpen(!open)}>
    ...
  </button>
</div>
```

```tsx
<div className={`workflow-stage workflow-stage-${stage.status}`}>
  <span className="workflow-stage-marker" />
  <span className="workflow-stage-label">{stage.label}</span>
</div>
```

Replace literal success and failure colors in `TaskRuntimeCard`, `AgentRunHeader`, and `AgentRunDetails` with status classes such as `status-running`, `status-success`, and `status-error`. Convert `VersionPanel` style-only wrappers to classes instead of adding new layout behavior.

- [ ] **Step 4: Convert CAD loading overlay states**

Keep progress percentages inline where they are data-driven, but use overlay classes for shell and status treatment:

```tsx
<div className="cad-loading-overlay cad-loading-overlay-error">
  <div className="cad-loading-symbol">&#x26A0;</div>
  <div className="cad-loading-title">{errorMessage}</div>
  <div className="cad-loading-copy">{stageLabel}</div>
</div>
```

```tsx
<div className="cad-loading-progress">
  <span className="cad-loading-progress-fill" style={{ width: `${progress}%` }} />
</div>
```

- [ ] **Step 5: Add shared runtime and CAD CSS**

Add:

```css
.runtime-notice {
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  background: var(--bg-surface);
}

.runtime-notice-info {
  border-color: var(--info-border);
  background: var(--info-bg);
}

.status-running { color: var(--accent-bright); }
.status-success { color: var(--success); }
.status-warning { color: var(--warning); }
.status-error { color: var(--error); }

.cad-loading-overlay {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, var(--bg-overlay) 84%, transparent);
}

.cad-loading-progress-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--accent-solid);
}
```

- [ ] **Step 6: Run runtime tests and full frontend tests**

Run:

```bash
cd "apps/web" && node --test --experimental-strip-types --test-name-pattern "runtime notices and cad overlays" "src/lib/uiStyleContract.test.ts"
cd "apps/web" && npm test
```

Expected: runtime contract and existing runtime, chat, and CAD helper tests pass.

- [ ] **Step 7: Commit**

```bash
git add "apps/web/src/lib/uiStyleContract.test.ts" "apps/web/src/app/globals.css" "apps/web/src/components/chat" "apps/web/src/components/runtime" "apps/web/src/components/cad-viewer/CADLoadingOverlay.tsx" "apps/web/src/components/version-panel/VersionPanel.tsx"
git commit -m "style: align runtime and cad feedback states"
```

## Task 6: Remove Legacy Palette Drift And Verify Browser States

**Files:**
- Modify: `apps/web/src/lib/uiStyleContract.test.ts`
- Modify: `apps/web/src/app/globals.css`
- Modify: affected frontend files if the audit finds remaining old palette fallbacks.

- [ ] **Step 1: Add a failing old-palette audit**

Append:

```ts
test("frontend style sources do not retain legacy cyan or blue fallbacks", () => {
  const files = [
    "app/globals.css",
    "components/chat/FallbackToolNotice.tsx",
    "components/runtime/DefaultedFieldsNotice.tsx",
    "components/cad-viewer/CADLoadingOverlay.tsx",
    "components/graph/RecommendedVariantCard.tsx",
    "components/graph/VariantThumbnail.tsx",
  ];

  for (const file of files) {
    const content = source(file);
    assert.doesNotMatch(content, /#06b6d4|#22d3ee|#3b82f6|#60a5fa|rgba\(6, 182, 212/);
  }
});
```

- [ ] **Step 2: Run the audit and verify it fails if drift remains**

Run:

```bash
cd "apps/web" && node --test --experimental-strip-types --test-name-pattern "legacy cyan or blue fallbacks" "src/lib/uiStyleContract.test.ts"
```

Expected: FAIL until remaining old palette fallbacks in the audited files are removed or mapped through semantic variables.

- [ ] **Step 3: Replace remaining audited drift with semantic tokens**

Replace legacy literals in the audited files with the token roles already established in earlier tasks. Do not expand the palette or add one-off feature colors. For example:

```css
.three-preview-canvas {
  background: radial-gradient(circle at 50% 35%, rgba(113, 112, 255, 0.12), transparent 50%);
}

.compare-status-pass { color: var(--success); }
.compare-status-warn { color: var(--warning); }
.compare-status-fail { color: var(--error); }
```

- [ ] **Step 4: Run full static verification**

Run:

```bash
cd "apps/web" && npm test
cd "apps/web" && npm run build
```

Expected: frontend test suite and production build pass.

- [ ] **Step 5: Start the frontend for browser QA**

Run:

```bash
cd "apps/web" && npm run dev
```

Expected: Next.js starts on `http://localhost:3900` unless the configured `WEB_PORT` overrides it. Keep the server running until browser QA is finished.

- [ ] **Step 6: Review critical browser states**

Use the browser QA path already available in the repo to inspect desktop and narrow viewport states:

1. Empty workspace with chat composer, CAD viewer empty state, parameter panel, Settings dropdown, and Compare drawer with zero items.
2. Compare drawer with one item and with at least two items, checking drawer header, notices, cards, table overflow, and action disabled states.
3. Deep Design form, running graph timeline, recommended variant card, and summary-card trust badge states.
4. CAD loading, CAD error, runtime task progress, defaulted-fields notice, workflow error card, and chat fallback notice.
5. A narrow viewport that exercises right-panel tabs, drawer width, button text wrapping, and table horizontal overflow.

Record any concrete regressions as targeted CSS or class cleanup before finalizing.

- [ ] **Step 7: Run final status checks and commit**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; status only includes intended UI implementation changes plus pre-existing untracked project artifacts that are not part of this task.

Commit:

```bash
git add "apps/web/src/lib/uiStyleContract.test.ts" "apps/web/src/app/globals.css" "apps/web/src"
git commit -m "style: finish design md ui unification"
```
