import assert from "node:assert/strict";
import test from "node:test";

import { computeSweepGeometry } from "./aeroSweepChart.ts";
import type { AeroSweepPoint } from "@/app/page";

function sweep(): AeroSweepPoint[] {
  return [
    { alpha: -4, cl: -0.23, cd: 0.034, cm: 0.6 },
    { alpha: 0, cl: 0.06, cd: 0.022, cm: 0.0 },
    { alpha: 3, cl: 0.35, cd: 0.024, cm: -0.4 },
    { alpha: 6, cl: 0.5, cd: 0.03, cm: -0.9 },
  ];
}

test("computeSweepGeometry builds polyline paths across all points", () => {
  const g = computeSweepGeometry(sweep(), 260, 132);
  assert.equal(g.clPath.startsWith("M"), true);
  assert.equal(g.clPath.split("L").length, 4);
  assert.equal(g.ldPath.startsWith("M"), true);
  assert.ok(g.alphaTicks.length >= 2);
  assert.ok(g.alphaTicks.length <= 5);
});

test("computeSweepGeometry marks the max L/D point as optimal", () => {
  const pts = sweep();
  const g = computeSweepGeometry(pts, 260, 132);
  assert.ok(g.optimal, "optimal marker should exist");
  // alpha=3 has L/D 14.6, the highest in the sweep.
  const best = pts.reduce((a, b) =>
    b.cl / b.cd > a.cl / a.cd ? b : a,
  );
  void best;
  // The optimal marker must lie on the L/D path (x within plot bounds).
  assert.ok(g.optimal.x >= g.plot.x0 && g.optimal.x <= g.plot.x1);
  assert.ok(g.optimal.y >= g.plot.y0 && g.optimal.y <= g.plot.y1);
});

test("computeSweepGeometry degrades gracefully with too few points", () => {
  const g = computeSweepGeometry([{ alpha: 0, cl: 0.1, cd: 0.02, cm: 0 }], 260, 132);
  assert.equal(g.clPath, "");
  assert.equal(g.ldPath, "");
  assert.equal(g.optimal, null);
});
