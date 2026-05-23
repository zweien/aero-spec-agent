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
  const css = source("app/globals.css");
  const activeCompareRule = css.match(
    /\.topbar-compare-active,[^}]*\.topbar-compare-active:hover:not\(:disabled\) \{[^}]*}/,
  )?.[0];

  assert.match(page, /className=\{`topbar-compare/);
  assert.doesNotMatch(page, /background: compareState\.items\.length/);

  assert.match(settings, /settings-profile-row/);
  assert.match(settings, /settings-preset/);
  assert.doesNotMatch(settings, /style=\{\{/);

  assert.match(metrics, /design-metrics-card/);
  assert.match(metrics, /risk-level-\$\{riskLevel\}/);
  assert.doesNotMatch(metrics, /style=\{\{/);

  assert.ok(activeCompareRule);
  assert.match(activeCompareRule, /border-color:\s*var\(--accent-border\);/);
  assert.match(activeCompareRule, /background:\s*var\(--accent-bg\);/);
  assert.match(activeCompareRule, /color:\s*var\(--accent-bright\);/);
  assert.match(css, /\.toolbar-button-danger:hover:not\(:disabled\) \{[^}]*color:\s*var\(--error\);/);
  assert.match(css, /\.settings-row \.settings-profile-select \{[^}]*font-size:\s*11px;/);
  assert.match(css, /\.settings-preset \{/);
  assert.match(css, /\.design-metrics-card \{/);
  assert.match(css, /\.risk-level-high \{\s*color:\s*var\(--error\);/);
});

test("compare view uses drawer and table class semantics", () => {
  const drawer = source("components/compare/CompareDrawer.tsx");
  const table = source("components/compare/CompareTable.tsx");
  const card = source("components/compare/CompareItemCard.tsx");
  const addButton = source("components/compare/AddToCompareButton.tsx");
  const metricCell = source("components/compare/CompareMetricCell.tsx");
  const css = source("app/globals.css");

  assert.match(drawer, /compare-drawer/);
  assert.match(drawer, /notice notice-info/);
  assert.match(table, /compare-table-scroll/);
  assert.match(card, /compare-item-card/);
  assert.doesNotMatch(drawer, /style=\{\{/);
  assert.doesNotMatch(table, /style=\{\{/);
  assert.doesNotMatch(card, /style=\{\{/);
  assert.doesNotMatch(addButton, /style=\{\{/);
  assert.doesNotMatch(metricCell, /style=\{\{/);
  assert.match(css, /\.compare-drawer \{/);
  assert.match(css, /\.compare-table-scroll \{/);
  assert.match(css, /\.compare-metric-cell \{/);
});

test("compare drawer and metric rows expose dialog and table semantics", () => {
  const drawer = source("components/compare/CompareDrawer.tsx");
  const table = source("components/compare/CompareTable.tsx");

  assert.match(drawer, /role="dialog"/);
  assert.match(drawer, /compare-drawer-scrim/);
  assert.match(drawer, /aria-modal="true"/);
  assert.match(drawer, /aria-labelledby="compare-drawer-title"/);
  assert.match(drawer, /id="compare-drawer-title"/);
  assert.match(drawer, /closeButtonRef\.current\?\.focus\(\)/);
  assert.match(drawer, /previousFocus\?\.focus\(\)/);
  assert.match(drawer, /event\.key === "Escape"/);
  assert.match(table, /<th scope="row" className="compare-metric-label">/);
});

test("deep design and graph cards use semantic class names", () => {
  const deepDesign = source("components/graph/DeepDesignPanel.tsx");
  const execution = source("components/graph/GraphExecutionPanel.tsx");
  const recommendation = source("components/graph/RecommendedVariantCard.tsx");
  const summary = source("components/graph/VariantSummaryCard.tsx");
  const thumbnail = source("components/graph/VariantThumbnail.tsx");
  const css = source("app/globals.css");
  const oldGraphUtilityClass =
    /className=(?:\{`|")[^"`\n]*\b(?:bg-(?:blue|green|red|gray|white)(?:-\d+)?|text-(?:blue|green|red|gray|white)(?:-\d+|\/\d+)?|flex(?:-\w+)?|items-center|gap-\d+|overflow-x-auto|pb-\d+|rounded(?:-\w+)?|border(?:-\w+)?|px-\d+|py-\d+|shadow-sm)\b/;

  assert.match(deepDesign, /deep-design-panel/);
  assert.match(execution, /graph-execution-panel/);
  assert.match(execution, /graph-node-timeline/);
  assert.match(execution, /<table className="graph-variant-table">/);
  assert.match(recommendation, /recommended-variant-card/);
  assert.match(summary, /variant-summary-card/);
  assert.match(thumbnail, /variant-thumbnail/);
  for (const graphSource of [deepDesign, execution, recommendation, summary, thumbnail]) {
    assert.doesNotMatch(graphSource, /style=\{\{/);
  }
  assert.doesNotMatch(execution, oldGraphUtilityClass);
  assert.doesNotMatch(recommendation, /rgba\(100,120,255/);
  assert.doesNotMatch(thumbnail, /rgba\(0,180,100|rgba\(220,50,50|rgba\(100,120,255/);
  assert.match(css, /\.deep-design-panel \{/);
  assert.match(css, /\.deep-design-section,/);
  assert.match(css, /\.graph-node-timeline \{/);
  assert.match(css, /\.graph-node-card \{/);
  assert.match(css, /\.graph-node-running \{/);
  assert.match(css, /\.graph-variant-table \{/);
  assert.match(css, /\.graph-variant-running \{/);
  assert.match(css, /\.recommended-variant-applying:disabled \{[^}]*background:\s*var\(--accent-solid\);/);
});

test("runtime notices and cad overlays use shared state classes", () => {
  const fallbackNotice = source("components/chat/FallbackToolNotice.tsx");
  const defaultedNotice = source("components/runtime/DefaultedFieldsNotice.tsx");
  const workflowError = source("components/runtime/WorkflowErrorCard.tsx");
  const cadOverlay = source("components/cad-viewer/CADLoadingOverlay.tsx");
  const taskRuntime = source("components/runtime/TaskRuntimeCard.tsx");
  const agentHeader = source("components/chat/AgentRunHeader.tsx");
  const agentDetails = source("components/chat/AgentRunDetails.tsx");
  const css = source("app/globals.css");

  assert.match(fallbackNotice, /runtime-notice runtime-notice-info/);
  assert.match(defaultedNotice, /runtime-notice runtime-notice-info/);
  for (const noticeSource of [fallbackNotice, defaultedNotice]) {
    assert.match(noticeSource, /type="button"/);
    assert.match(noticeSource, /aria-expanded=\{open\}/);
    assert.match(noticeSource, /aria-controls=\{detailsId\}/);
    assert.match(noticeSource, /id=\{detailsId\}/);
  }
  assert.match(defaultedNotice, /<th scope="col">参数<\/th>/);
  assert.match(workflowError, /workflow-error-card runtime-notice status-error/);
  assert.match(workflowError, /workflow-error-retry/);
  assert.match(cadOverlay, /cad-loading-overlay/);
  assert.match(cadOverlay, /cad-loading-overlay--error/);
  assert.match(cadOverlay, /cad-loading-overlay--compact/);
  assert.match(cadOverlay, /cad-loading-overlay--full/);
  assert.match(cadOverlay, /cad-loading-overlay-progress-fill/);
  const workflowTimeline = source("components/chat/WorkflowTimeline.tsx");
  const unifiedTimeline = source("components/runtime/UnifiedWorkflowTimeline.tsx");
  for (const timelineSource of [workflowTimeline, unifiedTimeline]) {
    assert.match(timelineSource, /<ol className=\{/);
    assert.match(timelineSource, /<li\s+[\s\S]*?key=/);
    assert.match(timelineSource, /aria-label=\{.*statusText/);
    assert.match(timelineSource, /aria-hidden="true"/);
    assert.match(timelineSource, /workflow-stage-running status-running/);
  }
  for (const migratedSource of [fallbackNotice, defaultedNotice, cadOverlay]) {
    assert.doesNotMatch(migratedSource, /#3b82f6|rgba\(59,\s*130,\s*246|#60a5fa/);
  }
  for (const runtimeSource of [taskRuntime, agentHeader, agentDetails]) {
    assert.doesNotMatch(runtimeSource, /#ef4444|#10b981|#e53e3e/);
  }
  assert.match(css, /\.runtime-notice \{/);
  assert.match(css, /\.runtime-notice-info \{/);
  assert.match(css, /\.cad-loading-overlay-error-title \{/);
  assert.match(css, /\.workflow-error-retry:hover:not\(:disabled\) \{/);
});

test("frontend style sources do not retain legacy cyan or blue fallbacks", () => {
  const files = [
    "app/globals.css",
    "components/chat/FallbackToolNotice.tsx",
    "components/runtime/DefaultedFieldsNotice.tsx",
    "components/cad-viewer/CADLoadingOverlay.tsx",
    "components/graph/RecommendedVariantCard.tsx",
    "components/graph/VariantThumbnail.tsx",
  ];
  const legacyPalette = /#06b6d4|#22d3ee|#3b82f6|#60a5fa|rgba\(6, 182, 212/;

  for (const file of files) {
    assert.doesNotMatch(source(file), legacyPalette, file);
  }
});
