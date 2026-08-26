"use client";

import { buildAircraftPreview, type AircraftPreviewSpec } from "./previewGeometry";

type TopViewThumbnailProps = {
  spec: AircraftPreviewSpec;
  className?: string;
};

// Miniature top-view silhouette reused for version chips, so each version in
// the history bar is recognisable at a glance instead of a bare "v3" label.
export function TopViewThumbnail({ spec, className = "version-thumb" }: TopViewThumbnailProps) {
  const preview = buildAircraftPreview(spec);
  return (
    <svg
      className={className}
      viewBox={preview.viewBox}
      aria-hidden="true"
      focusable="false"
    >
      <rect
        className="preview-fuselage"
        x={preview.top.fuselage.x}
        y={preview.top.fuselage.y}
        width={preview.top.fuselage.width}
        height={preview.top.fuselage.height}
        rx={preview.top.fuselage.radius}
        ry={preview.top.fuselage.radius}
      />
      <polygon className="preview-wing" points={preview.top.wing} />
      {preview.top.tail && <polygon className="preview-tail" points={preview.top.tail} />}
      {preview.top.engines.map((engine) => (
        <circle
          className="preview-engine"
          key={`${engine.cx}-${engine.cy}`}
          cx={engine.cx}
          cy={engine.cy}
          r={engine.r}
        />
      ))}
    </svg>
  );
}
