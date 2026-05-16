import assert from "node:assert/strict";
import test from "node:test";

import {
  buildPartRefsFromModel,
  shouldUsePickingOverlay,
} from "./pickingOverlay.ts";
import { buildAircraftThreeModel } from "./threePreviewModel.ts";
import type { AircraftPreviewSpec } from "./previewGeometry.ts";

const spec: AircraftPreviewSpec = {
  fuselage: {
    length: { value: 7.0, unit: "m" },
    max_diameter: { value: 0.75, unit: "m" },
  },
  wing: {
    position: { value: "high" },
    span: { value: 12.0, unit: "m" },
    root_chord: { value: 1.2, unit: "m" },
    tip_chord: { value: 0.6, unit: "m" },
  },
  tail: {
    type: { value: "conventional" },
  },
  engine: {
    count: { value: 2 },
  },
};

test("shouldUsePickingOverlay follows imported model load state", () => {
  assert.equal(shouldUsePickingOverlay(true), true);
  assert.equal(shouldUsePickingOverlay(false), false);
});

test("buildPartRefsFromModel preserves selectable part refs for imported model overlay", () => {
  const refs = buildPartRefsFromModel(buildAircraftThreeModel(spec));

  assert.deepEqual(refs, [
    "part:fuselage",
    "part:main_wing",
    "part:tail",
    "part:left_engine",
    "part:right_engine",
  ]);
});
