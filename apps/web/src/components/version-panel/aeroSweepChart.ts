import type { AeroSweepPoint } from "@/app/page";

export type SweepSeriesGeometry = {
  clPath: string;
  ldPath: string;
  optimal: { x: number; y: number } | null;
  alphaTicks: Array<{ x: number; label: string }>;
  plot: { x0: number; y0: number; x1: number; y1: number };
};

const PLOT_PADDING = { left: 34, right: 8, top: 8, bottom: 18 };

function niceBounds(min: number, max: number): [number, number] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, 1];
  if (min === max) return [min - 1, max + 1];
  return [min, max];
}

function formatTick(v: number): string {
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}

// Pure geometry for the aero sweep charts so it can be unit-tested without DOM.
export function computeSweepGeometry(
  points: AeroSweepPoint[],
  width: number,
  height: number,
): SweepSeriesGeometry {
  const sorted = [...points].sort((a, b) => a.alpha - b.alpha);
  const x0 = PLOT_PADDING.left;
  const x1 = width - PLOT_PADDING.right;
  const y0 = PLOT_PADDING.top;
  const y1 = height - PLOT_PADDING.bottom;

  if (sorted.length < 2) {
    return { clPath: "", ldPath: "", optimal: null, alphaTicks: [], plot: { x0, y0, x1, y1 } };
  }

  const alphas = sorted.map((p) => p.alpha);
  const [alphaMin, alphaMax] = niceBounds(Math.min(...alphas), Math.max(...alphas));

  const lds = sorted.map((p) => (p.cd > 1e-6 ? p.cl / p.cd : 0));
  const cls = sorted.map((p) => p.cl);
  const [clMin, clMax] = niceBounds(Math.min(...cls), Math.max(...cls));
  // Scale the L/D axis to positive values only — negative L/D segments are
  // not drawn (see below).
  const positiveLds = lds.filter((v) => v > 0);
  const [ldMin, ldMax] =
    positiveLds.length >= 2
      ? niceBounds(Math.min(...positiveLds), Math.max(...positiveLds))
      : [0, 1];

  const scaleX = (alpha: number) =>
    x0 + ((alpha - alphaMin) / (alphaMax - alphaMin)) * (x1 - x0);
  const scaleY = (v: number, vMin: number, vMax: number) =>
    y1 - ((v - vMin) / (vMax - vMin)) * (y1 - y0);

  const clPath = sorted
    .map((p, i) => `${i === 0 ? "M" : "L"}${scaleX(p.alpha).toFixed(1)},${scaleY(p.cl, clMin, clMax).toFixed(1)}`)
    .join(" ");
  // L/D is meaningless for negative CL; break the polyline into positive-only
  // segments so the chart doesn't draw a misleading dive through L/D ≤ 0.
  let ldPath = "";
  let inSegment = false;
  for (const p of sorted) {
    if (p.cd > 1e-6 && p.cl / p.cd > 0) {
      ldPath += `${inSegment ? "L" : "M"}${scaleX(p.alpha).toFixed(1)},${scaleY(p.cl / p.cd, ldMin, ldMax).toFixed(1)}`;
      inSegment = true;
    } else {
      inSegment = false;
    }
  }

  const optimalPoint = sorted.reduce<AeroSweepPoint | null>((best, p) => {
    if (p.cd <= 1e-6) return best;
    const ld = p.cl / p.cd;
    const bestLd = best && best.cd > 1e-6 ? best.cl / best.cd : -Infinity;
    return ld > bestLd ? p : best;
  }, null);

  const optimal =
    optimalPoint && optimalPoint.cd > 1e-6
      ? { x: scaleX(optimalPoint.alpha), y: scaleY(optimalPoint.cl / optimalPoint.cd, ldMin, ldMax) }
      : null;

  const tickCount = Math.min(5, sorted.length);
  const tickStep = Math.max(1, Math.floor((sorted.length - 1) / Math.max(1, tickCount - 1)));
  const alphaTicks: Array<{ x: number; label: string }> = [];
  for (let i = 0; i < sorted.length; i += tickStep) {
    alphaTicks.push({ x: scaleX(sorted[i].alpha), label: formatTick(sorted[i].alpha) });
  }

  return { clPath, ldPath, optimal, alphaTicks, plot: { x0, y0, x1, y1 } };
}
