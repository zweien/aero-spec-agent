"use client";

import React, { type JSX, useEffect, useMemo, useState } from "react";

type CADLoadingOverlayProps = {
  currentStage: string | null;
  progress: number;
  visible: boolean;
  artifacts?: string[];
  hasExistingModel?: boolean;
  error?: string | null;
};

const ARTIFACT_LABELS: Record<string, string> = {
  spec_file: "参数文件",
  fuselage: "机身",
  wing: "机翼",
  tail: "尾翼",
  engine: "发动机",
  vsp3: "VSP 模型",
  step: "STEP 文件",
  glb: "3D 模型",
  gltf: "3D 模型",
  obj: "OBJ 模型",
  report: "分析报告",
  validation: "验证报告",
  aero_analysis: "气动分析",
};

function artifactLabel(key: string): string {
  return ARTIFACT_LABELS[key] ?? key;
}

export function CADLoadingOverlay({
  currentStage,
  progress,
  visible,
  artifacts = [],
  hasExistingModel = false,
  error = null,
}: CADLoadingOverlayProps): JSX.Element | null {
  const [show, setShow] = useState(false);
  const [opacity, setOpacity] = useState(1);

  useEffect(() => {
    if (visible || error) {
      setShow(true);
      setOpacity(1);
    } else {
      setOpacity(0);
      const timer = setTimeout(() => setShow(false), 500);
      return () => clearTimeout(timer);
    }
  }, [visible, error]);

  // Reset show state when error is cleared and not visible
  useEffect(() => {
    if (!visible && !error) {
      setOpacity(0);
      const timer = setTimeout(() => setShow(false), 500);
      return () => clearTimeout(timer);
    }
  }, [visible, error]);

  const stageWithProgress = useMemo(() => {
    if (!currentStage) return null;
    if (progress > 0) {
      return `${currentStage} (${Math.round(progress)}%)`;
    }
    return currentStage;
  }, [currentStage, progress]);

  if (!show) return null;

  // Error state — always full overlay
  if (error && !visible) {
    return (
      <div
        className="cad-loading-overlay cad-loading-overlay--error"
        style={{
          opacity,
        }}
      >
        <div className="cad-loading-overlay-error-icon">&#x26A0;</div>
        <div className="cad-loading-overlay-error-title">
          生成失败
        </div>
        <div className="cad-loading-overlay-error-copy">
          {error}
        </div>
        <div className="cad-loading-overlay-error-note">
          之前的模型仍然可用
        </div>
      </div>
    );
  }

  // Compact overlay when a model already exists underneath
  if (hasExistingModel && visible) {
    return (
      <div
        className="cad-loading-overlay cad-loading-overlay--compact"
        style={{
          opacity,
          pointerEvents: opacity === 0 ? "none" : "auto",
        }}
      >
        <div className="cad-loading-overlay-running">
          {/* Spinner */}
          <div className="cad-loading-overlay-spinner" />
          {/* Stage text */}
          {stageWithProgress && (
            <div className="cad-loading-overlay-title">
              {stageWithProgress}
            </div>
          )}
          {/* Progress bar */}
          {progress > 0 && (
            <div className="cad-loading-overlay-progress cad-loading-overlay-progress-compact">
              <div className="cad-loading-overlay-progress-track">
                <div
                  className="cad-loading-overlay-progress-fill"
                  style={{
                    width: `${Math.min(progress, 100)}%`,
                  }}
                />
              </div>
            </div>
          )}
          {/* Mini artifact badges */}
          {artifacts.length > 0 && (
            <div className="cad-loading-overlay-artifacts cad-loading-overlay-artifacts-compact">
              {artifacts.map((a) => (
                <span key={a} className="cad-loading-overlay-artifact">
                  {artifactLabel(a)}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Full skeleton overlay (no existing model)
  return (
    <div
      className="cad-loading-overlay cad-loading-overlay--full"
      style={{
        opacity,
        pointerEvents: opacity === 0 ? "none" : "auto",
      }}
    >
      <div className="cad-loading-skeleton">
        <div className="cad-loading-skeleton-fuselage" />
        <div className="cad-loading-skeleton-engine" />
        <div className="cad-loading-skeleton-copy" />
      </div>
      {/* Stage label with progress */}
      {stageWithProgress && (
        <div className="cad-loading-overlay-copy">
          {stageWithProgress}
        </div>
      )}
      {/* Progress bar */}
      {progress > 0 && (
        <div className="cad-loading-overlay-progress cad-loading-overlay-progress-full">
          <div className="cad-loading-overlay-progress-track">
            <div
              className="cad-loading-overlay-progress-fill"
              style={{
                width: `${Math.min(progress, 100)}%`,
              }}
            />
          </div>
        </div>
      )}
      {/* Artifact list */}
      {artifacts.length > 0 && (
        <div className="cad-loading-overlay-artifacts">
          {artifacts.map((a) => (
            <span key={a} className="cad-loading-overlay-artifact">
              {artifactLabel(a)} &#x2713;
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
