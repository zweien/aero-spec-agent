"use client";

import React, { type JSX, useEffect, useState } from "react";

type CADLoadingOverlayProps = {
  currentStage: string | null;
  progress: number;
  visible: boolean;
};

export function CADLoadingOverlay({ currentStage, progress, visible }: CADLoadingOverlayProps): JSX.Element | null {
  const [show, setShow] = useState(false);
  const [opacity, setOpacity] = useState(1);

  useEffect(() => {
    if (visible) {
      setShow(true);
      setOpacity(1);
    } else {
      setOpacity(0);
      const timer = setTimeout(() => setShow(false), 500);
      return () => clearTimeout(timer);
    }
  }, [visible]);

  if (!show) return null;

  return (
    <div
      className="cad-loading-overlay"
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
        <div style={{ width: "120px", height: "40px", background: "var(--border-default)", borderRadius: "4px", marginBottom: "16px", animation: "pulse 2s ease-in-out infinite" }} />
        <div style={{ width: "80px", height: "80px", background: "var(--border-default)", borderRadius: "50%", marginBottom: "16px", animation: "pulse 2s ease-in-out infinite 0.3s" }} />
        <div style={{ width: "160px", height: "12px", background: "var(--border-default)", borderRadius: "2px", animation: "pulse 2s ease-in-out infinite 0.6s" }} />
      </div>
      {currentStage && (
        <div style={{ marginTop: "16px", fontSize: "13px", color: "var(--text-muted)" }}>
          {currentStage}
        </div>
      )}
      {progress > 0 && (
        <div style={{ marginTop: "8px", width: "160px" }}>
          <div
            style={{
              height: "4px",
              background: "var(--border-default)",
              borderRadius: "2px",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${Math.min(progress, 100)}%`,
                background: "var(--accent)",
                borderRadius: "2px",
                transition: "width 0.3s ease-out",
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
