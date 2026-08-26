"use client";

import type { AeroSweepPoint } from "@/app/page";
import { computeSweepGeometry } from "./aeroSweepChart";

const CHART_WIDTH = 260;
const CHART_HEIGHT = 132;

function SweepChart({
  title,
  path,
  geometry,
  showOptimal,
}: {
  title: string;
  path: string;
  geometry: ReturnType<typeof computeSweepGeometry>;
  showOptimal?: boolean;
}) {
  const { plot, alphaTicks } = geometry;
  return (
    <figure className="aero-chart">
      <figcaption>{title}</figcaption>
      <svg
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        role="img"
        aria-label={`${title}曲线图`}
      >
        <rect
          className="aero-chart-plot"
          x={plot.x0}
          y={plot.y0}
          width={plot.x1 - plot.x0}
          height={plot.y1 - plot.y0}
        />
        <line
          className="aero-chart-axis"
          x1={plot.x0}
          y1={plot.y1}
          x2={plot.x1}
          y2={plot.y1}
        />
        <line
          className="aero-chart-axis"
          x1={plot.x0}
          y1={plot.y0}
          x2={plot.x0}
          y2={plot.y1}
        />
        {alphaTicks.map((t) => (
          <g key={`${t.label}-${t.x}`}>
            <line
              className="aero-chart-tick"
              x1={t.x}
              y1={plot.y1}
              x2={t.x}
              y2={plot.y1 + 3}
            />
            <text className="aero-chart-tick-label" x={t.x} y={plot.y1 + 12}>
              {t.label}
            </text>
          </g>
        ))}
        <text className="aero-chart-axis-label" x={plot.x1} y={plot.y1 + 12}>
          α/°
        </text>
        {path ? <path className="aero-chart-line" d={path} /> : null}
        {showOptimal && geometry.optimal ? (
          <circle
            className="aero-chart-optimal"
            cx={geometry.optimal.x}
            cy={geometry.optimal.y}
            r={3}
          />
        ) : null}
      </svg>
    </figure>
  );
}

export function AeroSweepCharts({
  sweep,
  optimalAlpha,
}: {
  sweep: AeroSweepPoint[];
  optimalAlpha: number;
}) {
  const geometry = computeSweepGeometry(sweep, CHART_WIDTH, CHART_HEIGHT);
  return (
    <div className="aero-charts">
      <SweepChart
        title="CL – α"
        path={geometry.clPath}
        geometry={geometry}

      />
      <SweepChart
        title="L/D – α（圆点为最优点）"
        path={geometry.ldPath}
        geometry={geometry}

        showOptimal
      />
      <span className="aero-chart-optimal-note" data-optimal-alpha={optimalAlpha} />
    </div>
  );
}
