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
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "rgba(0,0,0,0.6)",
          opacity,
          transition: "opacity 0.5s ease-out",
          pointerEvents: "auto",
          zIndex: 10,
        }}
      >
        <div style={{ fontSize: "20px", marginBottom: "8px" }}>&#x26A0;</div>
        <div style={{ fontSize: "14px", color: "#f87171", fontWeight: 500, maxWidth: "260px", textAlign: "center" }}>
          生成失败
        </div>
        <div style={{ fontSize: "12px", color: "rgba(255,255,255,0.6)", marginTop: "4px", maxWidth: "260px", textAlign: "center" }}>
          {error}
        </div>
        <div style={{ fontSize: "11px", color: "rgba(255,255,255,0.4)", marginTop: "12px" }}>
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
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "rgba(0,0,0,0.55)",
          opacity,
          transition: "opacity 0.5s ease-out",
          pointerEvents: opacity === 0 ? "none" : "auto",
          zIndex: 10,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "8px" }}>
          {/* Spinner */}
          <div
            style={{
              width: "28px",
              height: "28px",
              border: "2px solid rgba(255,255,255,0.15)",
              borderTopColor: "var(--accent, #60a5fa)",
              borderRadius: "50%",
              animation: "cad-overlay-spin 0.8s linear infinite",
            }}
          />
          {/* Stage text */}
          {stageWithProgress && (
            <div style={{ fontSize: "13px", color: "rgba(255,255,255,0.85)", fontWeight: 500 }}>
              {stageWithProgress}
            </div>
          )}
          {/* Progress bar */}
          {progress > 0 && (
            <div style={{ width: "140px" }}>
              <div
                style={{
                  height: "3px",
                  background: "rgba(255,255,255,0.1)",
                  borderRadius: "2px",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    height: "100%",
                    width: `${Math.min(progress, 100)}%`,
                    background: "var(--accent, #60a5fa)",
                    borderRadius: "2px",
                    transition: "width 0.3s ease-out",
                  }}
                />
              </div>
            </div>
          )}
          {/* Mini artifact badges */}
          {artifacts.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", justifyContent: "center", maxWidth: "240px", marginTop: "4px" }}>
              {artifacts.map((a) => (
                <span
                  key={a}
                  style={{
                    fontSize: "10px",
                    padding: "2px 6px",
                    borderRadius: "3px",
                    background: "rgba(96, 165, 250, 0.15)",
                    color: "rgba(147, 197, 253, 0.9)",
                    border: "1px solid rgba(96, 165, 250, 0.2)",
                  }}
                >
                  {artifactLabel(a)}
                </span>
              ))}
            </div>
          )}
        </div>
        <style>{`
          @keyframes cad-overlay-spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }

  // Full skeleton overlay (no existing model)
  return (
    <div
      className="cad-loading-overlay cad-loading-overlay--full"
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--bg-secondary, rgba(0,0,0,0.05))",
        opacity,
        transition: "opacity 0.5s ease-out",
        pointerEvents: opacity === 0 ? "none" : "auto",
        zIndex: 10,
      }}
    >
      <div className="cad-loading-skeleton">
        <div
          style={{
            width: "120px",
            height: "40px",
            background: "var(--border-default, rgba(128,128,128,0.2))",
            borderRadius: "4px",
            marginBottom: "16px",
            animation: "cad-overlay-pulse 2s ease-in-out infinite",
          }}
        />
        <div
          style={{
            width: "80px",
            height: "80px",
            background: "var(--border-default, rgba(128,128,128,0.2))",
            borderRadius: "50%",
            marginBottom: "16px",
            animation: "cad-overlay-pulse 2s ease-in-out infinite 0.3s",
          }}
        />
        <div
          style={{
            width: "160px",
            height: "12px",
            background: "var(--border-default, rgba(128,128,128,0.2))",
            borderRadius: "2px",
            animation: "cad-overlay-pulse 2s ease-in-out infinite 0.6s",
          }}
        />
      </div>
      {/* Stage label with progress */}
      {stageWithProgress && (
        <div style={{ marginTop: "16px", fontSize: "13px", color: "var(--text-muted, #888)" }}>
          {stageWithProgress}
        </div>
      )}
      {/* Progress bar */}
      {progress > 0 && (
        <div style={{ marginTop: "8px", width: "160px" }}>
          <div
            style={{
              height: "4px",
              background: "var(--border-default, rgba(128,128,128,0.15))",
              borderRadius: "2px",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${Math.min(progress, 100)}%`,
                background: "var(--accent, #60a5fa)",
                borderRadius: "2px",
                transition: "width 0.3s ease-out",
              }}
            />
          </div>
        </div>
      )}
      {/* Artifact list */}
      {artifacts.length > 0 && (
        <div style={{ marginTop: "12px", display: "flex", flexWrap: "wrap", gap: "4px", justifyContent: "center", maxWidth: "280px" }}>
          {artifacts.map((a) => (
            <span
              key={a}
              style={{
                fontSize: "11px",
                padding: "2px 8px",
                borderRadius: "4px",
                background: "var(--border-default, rgba(128,128,128,0.1))",
                color: "var(--text-muted, #888)",
                border: "1px solid var(--border-default, rgba(128,128,128,0.15))",
              }}
            >
              {artifactLabel(a)} &#x2713;
            </span>
          ))}
        </div>
      )}
      <style>{`
        @keyframes cad-overlay-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
