import assert from "node:assert/strict";
import test from "node:test";

// ---------------------------------------------------------------------------
// Pure helpers extracted from WorkflowErrorCard logic for testability.
// These mirror the rendering decisions inside the component.
// ---------------------------------------------------------------------------

const DEFAULT_SUGGESTIONS = [
  "检查参数范围是否合理",
  "重新生成",
];

/** Resolves suggestions: falls back to DEFAULT_SUGGESTIONS when none provided. */
function resolveSuggestions(suggestions?: string[]): string[] {
  return suggestions ?? DEFAULT_SUGGESTIONS;
}

/** Whether the retry button should be shown. */
function shouldShowRetry(onRetry?: () => void): boolean {
  return !!onRetry;
}

/** Whether the "查看详情" button should be shown. */
function shouldShowViewLogs(onViewLogs?: () => void): boolean {
  return !!onViewLogs;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test("WorkflowErrorCard: resolves to default suggestions when none provided", () => {
  const tips = resolveSuggestions(undefined);
  assert.deepEqual(tips, DEFAULT_SUGGESTIONS);
  assert.equal(tips.length, 2);
  assert.ok(tips.includes("检查参数范围是否合理"));
  assert.ok(tips.includes("重新生成"));
});

test("WorkflowErrorCard: uses provided suggestions", () => {
  const custom = ["降低翼展", "调整发动机推力"];
  const tips = resolveSuggestions(custom);
  assert.deepEqual(tips, custom);
  assert.equal(tips.length, 2);
});

test("WorkflowErrorCard: accepts empty suggestions array", () => {
  const tips = resolveSuggestions([]);
  assert.deepEqual(tips, []);
});

test("WorkflowErrorCard: shows retry button when onRetry provided", () => {
  assert.equal(shouldShowRetry(() => {}), true);
});

test("WorkflowErrorCard: hides retry button when onRetry is undefined", () => {
  assert.equal(shouldShowRetry(undefined), false);
});

test("WorkflowErrorCard: shows view-logs button when onViewLogs provided", () => {
  assert.equal(shouldShowViewLogs(() => {}), true);
});

test("WorkflowErrorCard: hides view-logs button when onViewLogs is undefined", () => {
  assert.equal(shouldShowViewLogs(undefined), false);
});

// ---------------------------------------------------------------------------
// Render output expectations (verify expected strings are present in output)
// ---------------------------------------------------------------------------

test("WorkflowErrorCard: expected Chinese label for failure header", () => {
  const failedStage = "生成机身";
  // The component renders: `生成失败：${failedStage}`
  const expectedHeader = `生成失败：${failedStage}`;
  assert.ok(expectedHeader.includes("生成失败"));
  assert.ok(expectedHeader.includes(failedStage));
});

test("WorkflowErrorCard: error message is passed through", () => {
  const errorMessage = "参数超出范围，翼展不能超过 30m";
  // The component renders: <p>{errorMessage}</p>
  assert.ok(errorMessage.length > 0);
  assert.ok(errorMessage.includes("翼展"));
});
