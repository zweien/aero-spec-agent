"use client";

import {
  buildAircraftPreview,
  type AircraftPreviewSpec,
} from "./previewGeometry";

type CadViewerProps = {
  glbPath?: string;
  spec?: AircraftPreviewSpec | null;
};

export function CadViewer({ glbPath, spec }: CadViewerProps) {
  const preview = spec ? buildAircraftPreview(spec) : null;

  return (
    <section className="panel viewer-panel">
      <header>
        <span>CAD 预览</span>
        {preview ? (
          <small>
            {preview.labels.wingSpan} / {preview.labels.engineCount} 发
          </small>
        ) : null}
      </header>
      <div className="viewer-surface">
        {preview ? (
          <div className="aircraft-preview" aria-label="飞机几何预览">
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
            <div className="preview-metrics">
              <span>机身 {preview.labels.fuselageLength}</span>
              <span>翼展 {preview.labels.wingSpan}</span>
              <span>{preview.labels.wingPosition}</span>
            </div>
          </div>
        ) : (
          <span>等待生成模型</span>
        )}
        {glbPath ? <small className="artifact-note">GLB 占位文件：{glbPath}</small> : null}
      </div>
    </section>
  );
}
