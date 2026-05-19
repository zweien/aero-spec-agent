"use client";
import React, { type JSX } from "react";

export type VariantThumbnailProps = {
  label?: string;
};

export function VariantThumbnail({ label }: VariantThumbnailProps): JSX.Element {
  return (
    <div
      style={{
        width: 120,
        height: 80,
        background: "var(--bg-surface)",
        borderRadius: "var(--radius-sm)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
        overflow: "hidden",
        flexShrink: 0,
      }}
    >
      {/* Aircraft top-down silhouette */}
      <svg
        viewBox="0 0 120 80"
        width={120}
        height={80}
        style={{ position: "absolute", top: 0, left: 0 }}
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Fuselage */}
        <path
          d="M58 10 L62 10 L63 18 L64 50 L63 64 L61 70 L59 70 L57 64 L56 50 L57 18 Z"
          fill="var(--text-muted)"
          opacity={0.7}
        />
        {/* Main wing — left */}
        <path
          d="M56 36 L20 42 L18 44 L20 46 L56 42 Z"
          fill="var(--text-muted)"
          opacity={0.55}
        />
        {/* Main wing — right */}
        <path
          d="M64 36 L100 42 L102 44 L100 46 L64 42 Z"
          fill="var(--text-muted)"
          opacity={0.55}
        />
        {/* Horizontal tail — left */}
        <path
          d="M57 62 L34 66 L33 67 L34 68 L57 66 Z"
          fill="var(--text-muted)"
          opacity={0.5}
        />
        {/* Horizontal tail — right */}
        <path
          d="M63 62 L86 66 L87 67 L86 68 L63 66 Z"
          fill="var(--text-muted)"
          opacity={0.5}
        />
        {/* Vertical tail */}
        <path
          d="M58 58 L59 50 L60 46 L61 50 L62 58 L60 60 Z"
          fill="var(--text-muted)"
          opacity={0.6}
        />
        {/* Nose highlight */}
        <ellipse cx="60" cy="12" rx="2" ry="3" fill="var(--text-muted)" opacity={0.35} />
        {/* Engine nacelle — left */}
        <ellipse cx="36" cy="42" rx="3" ry="2" fill="var(--text-muted)" opacity={0.4} />
        {/* Engine nacelle — right */}
        <ellipse cx="84" cy="42" rx="3" ry="2" fill="var(--text-muted)" opacity={0.4} />
      </svg>
      {label && (
        <span
          style={{
            position: "absolute",
            bottom: 3,
            left: 0,
            right: 0,
            textAlign: "center",
            fontSize: 9,
            color: "var(--text-muted)",
            lineHeight: 1,
            pointerEvents: "none",
          }}
        >
          {label}
        </span>
      )}
    </div>
  );
}
