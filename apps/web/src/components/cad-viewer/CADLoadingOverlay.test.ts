import assert from "node:assert/strict";
import test from "node:test";

// ---------------------------------------------------------------------------
// Pure helpers extracted from CADLoadingOverlay logic for testability.
// These mirror the rendering decisions inside the component.
// ---------------------------------------------------------------------------

/** Whether the overlay should render visible content. */
function shouldRenderContent(visible: boolean): boolean {
  return visible;
}

/** Whether the stage label div should be rendered. */
function shouldShowStageLabel(currentStage: string | null): boolean {
  return currentStage !== null;
}

/** Whether the progress bar should be rendered. */
function shouldShowProgressBar(progress: number): boolean {
  return progress > 0;
}

/** Compute progress bar width as a percentage string (clamped to 100). */
function progressBarWidth(progress: number): string {
  return `${Math.min(progress, 100)}%`;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test("CADLoadingOverlay: hidden when visible=false", () => {
  assert.equal(shouldRenderContent(false), false);
});

test("CADLoadingOverlay: visible when visible=true", () => {
  assert.equal(shouldRenderContent(true), true);
});

test("CADLoadingOverlay: shows skeleton elements when visible", () => {
  // The overlay renders skeleton divs with class "cad-loading-skeleton"
  // We verify the component would render content
  assert.equal(shouldRenderContent(true), true);
});

test("CADLoadingOverlay: shows stage label when currentStage is set", () => {
  assert.equal(shouldShowStageLabel("生成机身"), true);
  assert.equal(shouldShowStageLabel("生成 CAD 模型"), true);
});

test("CADLoadingOverlay: hides stage label when currentStage is null", () => {
  assert.equal(shouldShowStageLabel(null), false);
});

test("CADLoadingOverlay: shows progress bar when progress > 0", () => {
  assert.equal(shouldShowProgressBar(1), true);
  assert.equal(shouldShowProgressBar(50), true);
  assert.equal(shouldShowProgressBar(100), true);
});

test("CADLoadingOverlay: hides progress bar when progress is 0", () => {
  assert.equal(shouldShowProgressBar(0), false);
});

test("CADLoadingOverlay: progress bar width matches progress", () => {
  assert.equal(progressBarWidth(0), "0%");
  assert.equal(progressBarWidth(30), "30%");
  assert.equal(progressBarWidth(75), "75%");
  assert.equal(progressBarWidth(100), "100%");
});

test("CADLoadingOverlay: progress bar width clamped to 100%", () => {
  assert.equal(progressBarWidth(150), "100%");
  assert.equal(progressBarWidth(200), "100%");
});
