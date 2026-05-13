import assert from "node:assert/strict";
import test from "node:test";

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

test("buildAircraftThreeModel maps spec dimensions into 3D aircraft parts", () => {
  const model = buildAircraftThreeModel(spec);

  assert.equal(model.fuselage.length, 7);
  assert.equal(model.wing.span, 12);
  assert.equal(model.wing.z > 0, true);
  assert.equal(model.engines.length, 2);
  assert.equal(model.engines[0].position.y, -model.engines[1].position.y);
  assert.equal(model.engines[0].finenessRatio, model.engines[1].finenessRatio);
  assert.equal(model.tail.vertical.rotation.x, Math.PI / 2);
});

test("buildAircraftThreeModel uses stable defaults for optional geometry", () => {
  const model = buildAircraftThreeModel({
    ...spec,
    fuselage: {
      length: { value: 7.0, unit: "m" },
      max_diameter: null,
    },
    wing: {
      ...spec.wing,
      position: { value: "unknown" },
    },
  });

  assert.equal(model.fuselage.diameter, 0.75);
  assert.equal(model.wing.z, 0);
});
