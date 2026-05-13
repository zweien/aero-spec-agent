import {
  numberValue,
  textValue,
  type AircraftPreviewSpec,
  wingZ,
} from "./previewGeometry.ts";

type Vec3 = {
  x: number;
  y: number;
  z: number;
};

type Rot3 = {
  x: number;
  y: number;
  z: number;
};

export type AircraftThreeModel = {
  fuselage: {
    length: number;
    diameter: number;
  };
  wing: {
    span: number;
    rootChord: number;
    tipChord: number;
    z: number;
  };
  tail: {
    horizontal: {
      span: number;
      chord: number;
      position: Vec3;
    };
    vertical: {
      span: number;
      chord: number;
      position: Vec3;
      rotation: Rot3;
    };
  };
  engines: Array<{
    length: number;
    diameter: number;
    finenessRatio: number;
    position: Vec3;
  }>;
};

export function buildAircraftThreeModel(spec: AircraftPreviewSpec): AircraftThreeModel {
  const fuselageLength = numberValue(spec.fuselage.length, 7);
  const fuselageDiameter = numberValue(spec.fuselage.max_diameter, 0.75);
  const wingSpan = numberValue(spec.wing.span, 12);
  const rootChord = numberValue(spec.wing.root_chord, 1.2);
  const tipChord = numberValue(spec.wing.tip_chord, 0.6);
  const position = textValue(spec.wing.position, "mid");
  const engineCount = Math.max(0, Math.round(numberValue(spec.engine.count, 0)));
  const nacelleDiameter = fuselageDiameter * 0.5;
  const nacelleLength = rootChord;
  const radius = nacelleDiameter / 2;
  const finenessRatio = radius > 0 ? nacelleLength / radius : 0;
  const engineY = wingSpan * 0.25;
  const enginePosition = {
    x: rootChord * 0.25,
    z: -fuselageDiameter * 0.45,
  };

  return {
    fuselage: {
      length: fuselageLength,
      diameter: fuselageDiameter,
    },
    wing: {
      span: wingSpan,
      rootChord,
      tipChord,
      z: wingZ(position, fuselageDiameter),
    },
    tail: {
      horizontal: {
        span: wingSpan * 0.28,
        chord: rootChord * 0.45,
        position: { x: fuselageLength * 0.42, y: 0, z: 0 },
      },
      vertical: {
        span: wingSpan * 0.16,
        chord: rootChord * 0.55,
        position: { x: fuselageLength * 0.42, y: 0, z: fuselageDiameter * 0.4 },
        rotation: { x: Math.PI / 2, y: 0, z: 0 },
      },
    },
    engines:
      engineCount >= 2
        ? [
            {
              length: nacelleLength,
              diameter: nacelleDiameter,
              finenessRatio,
              position: { x: enginePosition.x, y: -engineY, z: enginePosition.z },
            },
            {
              length: nacelleLength,
              diameter: nacelleDiameter,
              finenessRatio,
              position: { x: enginePosition.x, y: engineY, z: enginePosition.z },
            },
          ]
        : [],
  };
}
