import assert from "node:assert/strict";
import test from "node:test";

import { buildAircraftPreview, type AircraftPreviewSpec } from "./previewGeometry.ts";

const twinEngineSpec: AircraftPreviewSpec = {
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

test("buildAircraftPreview maps the example UAV into visible aircraft geometry", () => {
  const preview = buildAircraftPreview(twinEngineSpec);

  assert.equal(preview.dimensions.wingSpan, 12);
  assert.equal(preview.dimensions.fuselageLength, 7);
  assert.equal(preview.dimensions.engineCount, 2);
  assert.equal(preview.labels.wingSpan, "12 m");
  assert.equal(preview.top.engines.length, 2);
  assert.equal(preview.top.engines[0].cy < 0, true);
  assert.equal(preview.top.engines[1].cy > 0, true);
  assert.equal(preview.side.wingZ > 0, true);
});

test("buildAircraftPreview falls back to safe MVP defaults for optional values", () => {
  const preview = buildAircraftPreview({
    ...twinEngineSpec,
    fuselage: {
      length: { value: 7.0, unit: "m" },
      max_diameter: null,
    },
    wing: {
      ...twinEngineSpec.wing,
      position: { value: "unknown" },
    },
  });

  assert.equal(preview.dimensions.fuselageDiameter, 0.75);
  assert.equal(preview.side.wingZ, 0);
});
