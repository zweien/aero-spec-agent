"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { AircraftThreePreview } from "./AircraftThreePreview";
import { CADLoadingOverlay } from "./CADLoadingOverlay";
import type { CadPreviewFormat } from "./cadPreviewSource";
import {
  cadPreviewStatusLabel,
  type CadPreviewStatus,
} from "./cadPreviewStatus";
import {
  buildAircraftPreview,
  type AircraftPreviewSpec,
  type PreviewElement,
} from "./previewGeometry";

type CadViewerRuntimeStatus = {
  status: "idle" | "running" | "completed" | "failed";
  currentStageLabel?: string;
  progress?: number;
  artifacts?: string[];
  error?: string | null;
};

type CadViewerProps = {
  modelFormat?: CadPreviewFormat;
  modelUrl?: string;
  onSelectPart?: (partRef: string | null) => void;
  spec?: AircraftPreviewSpec | null;
  /** @deprecated Use runtimeStatus instead */
  generationStage?: string | null;
  /** @deprecated Use runtimeStatus instead */
  generationProgress?: number;
  /** @deprecated Use runtimeStatus instead */
  isGenerating?: boolean;
  runtimeStatus?: CadViewerRuntimeStatus;
};

function renderElement(el: PreviewElement, idx: number) {
  switch (el.kind) {
    case "polygon":
      return <polygon className={el.className} points={el.points} key={`el-${idx}`} />;
    case "rect":
      return (
        <rect
          className={el.className}
          x={el.x} y={el.y}
          width={el.width} height={el.height}
          rx={el.radius} ry={el.radius}
          key={`el-${idx}`}
        />
      );
    case "circle":
      return (
        <circle
          className={el.className}
          cx={el.cx} cy={el.cy} r={el.r}
          key={`el-${idx}`}
        />
      );
  }
}

export function CadViewer({ modelFormat, modelUrl, onSelectPart, spec, generationStage, generationProgress, isGenerating, runtimeStatus }: CadViewerProps) {
  const [previewStatus, setPreviewStatus] = useState<CadPreviewStatus>({ state: "parameter" });
  const [drawingsPct, setDrawingsPct] = useState(28);
  const [topPct, setTopPct] = useState(50);
  const preview = spec ? buildAircraftPreview(spec) : null;
  const surfaceRef = useRef<HTMLDivElement>(null);
  const drawingsRef = useRef<HTMLDivElement>(null);
  const dragTarget = useRef<"surface" | "drawings" | null>(null);

  const handleStatusChange = useCallback((status: CadPreviewStatus) => {
    setPreviewStatus(status);
  }, []);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (dragTarget.current === "surface" && surfaceRef.current) {
        const rect = surfaceRef.current.getBoundingClientRect();
        const pct = ((rect.bottom - e.clientY) / rect.height) * 100;
        setDrawingsPct(Math.max(10, Math.min(55, pct)));
      } else if (dragTarget.current === "drawings" && drawingsRef.current) {
        const rect = drawingsRef.current.getBoundingClientRect();
        const pct = ((e.clientX - rect.left) / rect.width) * 100;
        setTopPct(Math.max(15, Math.min(85, pct)));
      }
    };
    const onUp = () => {
      dragTarget.current = null;
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

  const startDrag = useCallback((target: "surface" | "drawings") => {
    dragTarget.current = target;
    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";
  }, []);

  // Derive overlay props: prefer runtimeStatus, fall back to legacy props
  const overlayVisible = runtimeStatus
    ? runtimeStatus.status === "running" || (runtimeStatus.status === "failed" && !!runtimeStatus.error)
    : (isGenerating ?? false);
  const overlayStage = runtimeStatus
    ? (runtimeStatus.currentStageLabel ?? null)
    : (generationStage ?? null);
  const overlayProgress = runtimeStatus
    ? (runtimeStatus.progress ?? 0)
    : (generationProgress ?? 0);
  const overlayArtifacts = runtimeStatus
    ? (runtimeStatus.artifacts ?? [])
    : [];
  const overlayError = runtimeStatus
    ? (runtimeStatus.status === "failed" ? runtimeStatus.error : null)
    : null;
  // hasExistingModel: true if we have a real model loaded (url present) or spec-based preview
  const hasExistingModel = !!(modelUrl || spec);

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
                onSelectPart={onSelectPart}
                onStatusChange={handleStatusChange}
                spec={spec}
              />
              <span className="preview-source-status">
                {cadPreviewStatusLabel(previewStatus)}
              </span>
            </div>
            <div
              className="resize-handle-h"
              onMouseDown={() => startDrag("surface")}
            />
            <div
              className="preview-drawings"
              ref={drawingsRef}
              style={{ flex: `0 0 ${drawingsPct}%` }}
            >
              <div
                className="preview-top-wrap"
                style={{ flex: `1 1 ${topPct}%` }}
              >
                <svg className="preview-top" viewBox={preview.viewBox} role="img">
                  <title>飞机俯视预览</title>
                  <line className="preview-axis" x1="0" y1="-7" x2="0" y2="7" />
                  {preview.top.underlays.map((el, i) => renderElement(el, i))}
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
                  {preview.top.overlays.map((el, i) => renderElement(el, i))}
                </svg>
              </div>
              <div
                className="resize-handle-v"
                onMouseDown={() => startDrag("drawings")}
              />
              <div
                className="preview-side-wrap"
                style={{ flex: `1 1 ${100 - topPct}%` }}
              >
                <svg className="preview-side" viewBox={preview.sideViewBox} role="img">
                  <title>飞机侧视预览</title>
                  <line className="preview-ground" x1="-4.2" y1="1.05" x2="4.2" y2="1.05" />
                  {preview.side.underlays.map((el, i) => renderElement(el, i))}
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
                  {preview.side.tail && <polygon className="preview-tail" points={preview.side.tail} />}
                  {preview.side.engines.map((engine) => (
                    <circle
                      className="preview-engine"
                      key={`${engine.cx}-${engine.cy}`}
                      cx={engine.cx}
                      cy={engine.cy}
                      r={engine.r}
                    />
                  ))}
                  {preview.side.overlays.map((el, i) => renderElement(el, i))}
                </svg>
              </div>
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
        <CADLoadingOverlay
          currentStage={overlayStage}
          progress={overlayProgress}
          visible={overlayVisible}
          artifacts={overlayArtifacts}
          hasExistingModel={hasExistingModel}
          error={overlayError}
        />
      </div>
    </section>
  );
}
