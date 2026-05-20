/**
 * Pure helpers for TaskRuntimeCard — tested independently of React rendering.
 *
 * These functions compute the CSS class, header icon text, and artifact URL
 * so that the card's conditional rendering logic is verifiable without JSX.
 */

export type TaskRuntimeState = {
  isRunning: boolean;
  isFailed: boolean;
  progress: number;
  versionNo?: number;
  artifacts: string[];
  apiBaseUrl?: string;
  designId?: string;
  failedStageLabel?: string;
  errorMessage?: string;
};

/** Returns the CSS class string for the card container. */
export function cardClassName(state: TaskRuntimeState): string {
  if (state.isRunning) return "tool-card tool-card-running";
  if (state.isFailed) return "tool-card tool-card-failed";
  return "tool-card tool-card-done";
}

/** Returns the header icon character. */
export function headerIcon(state: TaskRuntimeState): string {
  if (state.isRunning) return "spinner";
  if (state.isFailed) return "✗";
  return "✓";
}

/** Returns true if the progress bar should be shown. */
export function shouldShowProgressBar(state: TaskRuntimeState): boolean {
  return state.isRunning && state.progress > 0;
}

/** Returns true if artifact links should be shown. */
export function shouldShowArtifacts(state: TaskRuntimeState): boolean {
  const isCompleted = !state.isRunning && !state.isFailed;
  return isCompleted && state.artifacts.length > 0 && state.versionNo != null && !!state.apiBaseUrl && !!state.designId;
}

/** Builds the version file download URL for a given artifact. */
export function buildArtifactUrl(state: TaskRuntimeState, filename: string): string {
  return `${state.apiBaseUrl}/api/designs/${state.designId}/versions/${state.versionNo}/files/${encodeURIComponent(filename)}`;
}

/** Returns the failed stage label or a default. */
export function failedStage(state: TaskRuntimeState): string {
  return state.failedStageLabel ?? "未知阶段";
}

/** Returns the error message or a default. */
export function failedMessage(state: TaskRuntimeState): string {
  return state.errorMessage ?? "生成失败";
}

/** Formats progress as a rounded percentage string. */
export function formatProgress(progress: number): string {
  return `${Math.round(progress)}%`;
}

// ---------------------------------------------------------------------------
// Artifact label mapping
// ---------------------------------------------------------------------------

const ARTIFACT_LABELS: Record<string, string> = {
  vsp3: "3D 模型",
  step: "STEP 工程",
  glb: "3D 预览",
  obj: "OBJ 模型",
  report: "分析报告",
};

/** Returns a localized label for an artifact key. */
export function getArtifactLabel(key: string): string {
  return ARTIFACT_LABELS[key] ?? key;
}

// ---------------------------------------------------------------------------
// Artifact HTML builder
// ---------------------------------------------------------------------------

/**
 * Builds an HTML string for the artifact section shown when the card is
 * completed and artifacts are present.  This allows tests to verify the
 * rendering logic without React.
 */
export function buildArtifactHtml(artifacts: string[]): string {
  if (artifacts.length === 0) return "";

  const header = `已生成 ${artifacts.length} 个文件`;
  const badges = artifacts
    .map((key) => `<span class="artifact-badge">${getArtifactLabel(key)}</span>`)
    .join("");

  return `<div class="tool-card-artifacts"><div class="artifact-header">${header}</div><div class="artifact-list">${badges}</div></div>`;
}
