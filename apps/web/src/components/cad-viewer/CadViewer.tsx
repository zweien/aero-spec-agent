"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { AircraftThreePreview } from "./AircraftThreePreview";
import type { CadPreviewFormat } from "./cadPreviewSource";
import {
  cadPreviewStatusLabel,
  type CadPreviewStatus,
} from "./cadPreviewStatus";
import {
  buildAircraftPreview,
  type AircraftPreviewSpec,
} from "./previewGeometry";

type CadViewerProps = {
  modelFormat?: CadPreviewFormat;
  modelUrl?: string;
  spec?: AircraftPreviewSpec | null;
};

export function CadViewer({ modelFormat, modelUrl, spec }: CadViewerProps) {
  const [previewStatus, setPreviewStatus] = useState<CadPreviewStatus>({ state: "parameter" });
  const [drawingsPct, setDrawingsPct] = useState(28);
  const preview = spec ? buildAircraftPreview(spec) : null;
  const surfaceRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const handleStatusChange = useCallback((status: CadPreviewStatus) => {
    setPreviewStatus(status);
  }, []);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current || !surfaceRef.current) return;
      const rect = surfaceRef.current.getBoundingClientRect();
      const pct = ((rect.bottom - e.clientY) / rect.height) * 100;
      setDrawingsPct(Math.max(10, Math.min(55, pct)));
    };
    const onUp = () => {
      dragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  const handleDragStart = useCallback(() => {
    dragging.current = true;
    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";
  }, []);

  return (
    <section className="panel viewer-panel">
      <header>
        <span>CAD 预览</span>
        {spec && preview ? (
          <small>
            {preview.labels.wingSpan} / {preview.labels.engineCount} 发
          </small>
        ) : null}
      </header>
      <div className="viewer-surface" ref={surfaceRef}>
        {spec && preview ? (
          <div className="aircraft-preview" aria-label="飞机几何预览">
            <div
              className="three-preview-frame"
              style={{ flex: `1 1 ${100 - drawingsPct}%` }}
            >
              <AircraftThreePreview
                modelFormat={modelFormat}
                modelUrl={modelUrl}
                onStatusChange={handleStatusChange}
                spec={spec}
              />
              <span className="preview-source-status">
                {cadPreviewStatusLabel(previewStatus)}
              </span>
            </div>
            <div
              className="resize-handle-h"
              onMouseDown={handleDragStart}
            />
            <div
              className="preview-drawings"
              style={{ flex: `0 0 ${drawingsPct}%` }}
            >
              <svg className="preview-top" viewBox={preview.viewBox} role="img">
                <title>飞机俯视预览</title>
                <line className="preview-axis" x1="0" y1="-7" x2="0" y2="7" />
                <polygon className="preview-wing" points={preview.top.wing} />
                <rect
                  className="preview-fuselage"
                  x={preview.top.fuselage.x}
                  y={preview.top.fuselage.y}
                  width={preview.top.fuselage.width}
                  height={preview.top.fuselage.height}
                  rx={preview.top.fuselage.radius}
                  ry={preview.top.fuselage.radius}
                />
                <polygon className="preview-tail" points={preview.top.tail} />
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
              <svg className="preview-side" viewBox="-4.2 -1.4 8.4 2.8" role="img">
                <title>飞机侧视预览</title>
                <line className="preview-ground" x1="-4.2" y1="1.05" x2="4.2" y2="1.05" />
                <rect
                  className="preview-fuselage"
                  x={preview.side.fuselage.x}
                  y={preview.side.fuselage.y}
                  width={preview.side.fuselage.width}
                  height={preview.side.fuselage.height}
                  rx={preview.side.fuselage.radius}
                  ry={preview.side.fuselage.radius}
                />
                <polygon className="preview-wing" points={preview.side.wing} />
                <polygon className="preview-tail" points={preview.side.tail} />
                {preview.side.engines.map((engine) => (
                  <circle
                    className="preview-engine"
                    key={`${engine.cx}-${engine.cy}`}
                    cx={engine.cx}
                    cy={engine.cy}
                    r={engine.r}
                  />
                ))}
              </svg>
            </div>
            <div className="preview-metrics">
              <span>机身 {preview.labels.fuselageLength}</span>
              <span>翼展 {preview.labels.wingSpan}</span>
              <span>{preview.labels.wingPosition}</span>
            </div>
          </div>
        ) : (
          <span>等待生成模型</span>
        )}
      </div>
    </section>
  );
}
