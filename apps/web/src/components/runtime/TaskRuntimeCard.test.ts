import assert from "node:assert/strict";
import test from "node:test";

import {
  cardClassName,
  headerIcon,
  shouldShowProgressBar,
  shouldShowArtifacts,
  buildArtifactUrl,
  failedStage,
  failedMessage,
  formatProgress,
  getArtifactLabel,
  buildArtifactHtml,
  type TaskRuntimeState,
} from "./taskRuntimeCardHtml.ts";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test("TaskRuntimeCard renders running state with timeline", () => {
  const state: TaskRuntimeState = {
    isRunning: true,
    isFailed: false,
    progress: 0,
    artifacts: [],
  };

  assert.equal(cardClassName(state), "tool-card tool-card-running");
  assert.equal(headerIcon(state), "spinner");
  // Running with progress 0 should NOT show progress bar
  assert.equal(shouldShowProgressBar(state), false);
  // Running should not show artifacts
  assert.equal(shouldShowArtifacts(state), false);
});

test("TaskRuntimeCard renders completed state with artifacts list", () => {
  const state: TaskRuntimeState = {
    isRunning: false,
    isFailed: false,
    progress: 100,
    versionNo: 3,
    artifacts: ["aircraft.glb", "aircraft.step"],
    apiBaseUrl: "http://localhost:3900",
    designId: "design-abc",
  };

  assert.equal(cardClassName(state), "tool-card tool-card-done");
  assert.equal(headerIcon(state), "✓");
  assert.equal(shouldShowArtifacts(state), true);

  // Artifact URLs are built correctly
  const url = buildArtifactUrl(state, "aircraft.glb");
  assert.equal(url, "http://localhost:3900/api/designs/design-abc/versions/3/files/aircraft.glb");

  // Version badge text
  assert.equal(`v${state.versionNo}`, "v3");
});

test("TaskRuntimeCard renders failed state with error card", () => {
  const state: TaskRuntimeState = {
    isRunning: false,
    isFailed: true,
    progress: 50,
    artifacts: [],
    failedStageLabel: "生成模型",
    errorMessage: "参数超出范围",
  };

  assert.equal(cardClassName(state), "tool-card tool-card-failed");
  assert.equal(headerIcon(state), "✗");
  assert.equal(failedStage(state), "生成模型");
  assert.equal(failedMessage(state), "参数超出范围");

  // Failed state should not show artifacts even if present
  const stateWithFiles = { ...state, artifacts: ["test.glb"], versionNo: 1, apiBaseUrl: "http://x", designId: "d" };
  assert.equal(shouldShowArtifacts(stateWithFiles), false);
});

test("TaskRuntimeCard renders progress bar when running", () => {
  const state: TaskRuntimeState = {
    isRunning: true,
    isFailed: false,
    progress: 65,
    artifacts: [],
  };

  assert.equal(shouldShowProgressBar(state), true);
  assert.equal(formatProgress(state.progress), "65%");

  // Progress at 100 while running
  const stateDone = { ...state, progress: 100 };
  assert.equal(shouldShowProgressBar(stateDone), true);
  assert.equal(formatProgress(stateDone.progress), "100%");

  // Progress at 0 while running — bar hidden
  const stateZero = { ...state, progress: 0 };
  assert.equal(shouldShowProgressBar(stateZero), false);
});

// ---------------------------------------------------------------------------
// Artifact list tests
// ---------------------------------------------------------------------------

test("test_artifact_list_shows_when_artifacts_present", () => {
  const state: TaskRuntimeState = {
    isRunning: false,
    isFailed: false,
    progress: 100,
    versionNo: 1,
    artifacts: ["vsp3", "step", "glb"],
    apiBaseUrl: "http://localhost:3900",
    designId: "design-1",
  };

  assert.equal(shouldShowArtifacts(state), true);

  const html = buildArtifactHtml(state.artifacts);
  assert.ok(html.length > 0, "artifact HTML should not be empty when artifacts are present");
  assert.ok(html.includes("tool-card-artifacts"), "should contain the artifacts container");
  assert.ok(html.includes("artifact-header"), "should contain the header");
  assert.ok(html.includes("已生成 3 个文件"), "should show the correct count");
  assert.ok(html.includes("artifact-badge"), "should contain artifact badges");
});

test("test_artifact_list_hidden_when_no_artifacts", () => {
  const state: TaskRuntimeState = {
    isRunning: false,
    isFailed: false,
    progress: 100,
    artifacts: [],
  };

  // No artifacts → shouldShowArtifacts returns false
  assert.equal(shouldShowArtifacts(state), false);

  // buildArtifactHtml returns empty string
  const html = buildArtifactHtml([]);
  assert.equal(html, "", "artifact HTML should be empty when no artifacts");
});

test("test_artifact_labels_are_localized", () => {
  // Known artifact keys get localized labels
  assert.equal(getArtifactLabel("vsp3"), "3D 模型");
  assert.equal(getArtifactLabel("step"), "STEP 工程");
  assert.equal(getArtifactLabel("glb"), "3D 预览");
  assert.equal(getArtifactLabel("obj"), "OBJ 模型");
  assert.equal(getArtifactLabel("report"), "分析报告");

  // Unknown keys fall back to the key itself
  assert.equal(getArtifactLabel("unknown_type"), "unknown_type");
  assert.equal(getArtifactLabel("custom"), "custom");

  // buildArtifactHtml uses the localized labels
  const html = buildArtifactHtml(["glb", "step"]);
  assert.ok(html.includes("3D 预览"), "should contain localized glb label");
  assert.ok(html.includes("STEP 工程"), "should contain localized step label");
});
