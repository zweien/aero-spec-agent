type Scalar = {
  value: string | number;
  unit?: string | null;
};

export type AircraftPreviewSpec = {
  fuselage: {
    length: Scalar;
    max_diameter?: Scalar | null;
  };
  wing: {
    position: Scalar;
    span: Scalar;
    root_chord: Scalar;
    tip_chord: Scalar;
  };
  tail: {
    type: Scalar;
  };
  engine: {
    count: Scalar;
  };
};

type Circle = {
  cx: number;
  cy: number;
  r: number;
};

export type AircraftPreview = {
  dimensions: {
    fuselageDiameter: number;
    fuselageLength: number;
    wingSpan: number;
    engineCount: number;
  };
  labels: {
    wingSpan: string;
    fuselageLength: string;
    engineCount: string;
    wingPosition: string;
  };
  viewBox: string;
  top: {
    fuselage: {
      x: number;
      y: number;
      width: number;
      height: number;
      radius: number;
    };
    wing: string;
    tail: string;
    engines: Circle[];
  };
  side: {
    fuselage: {
      x: number;
      y: number;
      width: number;
      height: number;
      radius: number;
    };
    wing: string;
    tail: string;
    engines: Circle[];
    wingZ: number;
  };
};

export function numberValue(scalar: Scalar | null | undefined, fallback: number): number {
  const value = Number(scalar?.value);
  return Number.isFinite(value) ? value : fallback;
}

export function textValue(scalar: Scalar | null | undefined, fallback: string): string {
  const value = scalar?.value;
  return typeof value === "string" && value.trim() ? value.trim().toLowerCase() : fallback;
}

export function wingZ(position: string, fuselageDiameter: number): number {
  if (position === "high") {
    return fuselageDiameter * 0.45;
  }
  if (position === "low") {
    return -fuselageDiameter * 0.45;
  }
  return 0;
}

function wingPositionLabel(position: string): string {
  if (position === "high") {
    return "上单翼";
  }
  if (position === "low") {
    return "下单翼";
  }
  if (position === "mid") {
    return "中单翼";
  }
  return "机翼位置待定";
}

function polygon(points: Array<[number, number]>): string {
  return points.map(([x, y]) => `${x},${y}`).join(" ");
}

function metersLabel(value: number): string {
  return `${Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1)} m`;
}

export function buildAircraftPreview(spec: AircraftPreviewSpec): AircraftPreview {
  const fuselageLength = numberValue(spec.fuselage.length, 7);
  const fuselageDiameter = numberValue(spec.fuselage.max_diameter, 0.75);
  const wingSpan = numberValue(spec.wing.span, 12);
  const rootChord = numberValue(spec.wing.root_chord, 1.2);
  const tipChord = numberValue(spec.wing.tip_chord, 0.6);
  const engineCount = Math.max(0, Math.round(numberValue(spec.engine.count, 0)));
  const position = textValue(spec.wing.position, "mid");
  const halfLength = fuselageLength / 2;
  const halfSpan = wingSpan / 2;
  const topMargin = 0.7;
  const topViewSize = Math.max(fuselageLength, wingSpan) + topMargin * 2;
  const wingX = -fuselageLength * 0.08;
  const tailX = halfLength * 0.72;
  const tailSpan = wingSpan * 0.28;
  const engineY = wingSpan * 0.25;
  const engineRadius = Math.max(fuselageDiameter * 0.22, 0.12);
  const engineX = wingX + rootChord * 0.25;
  const z = wingZ(position, fuselageDiameter);

  return {
    dimensions: {
      fuselageDiameter,
      fuselageLength,
      wingSpan,
      engineCount,
    },
    labels: {
      wingSpan: metersLabel(wingSpan),
      fuselageLength: metersLabel(fuselageLength),
      engineCount: `${engineCount}`,
      wingPosition: wingPositionLabel(position),
    },
    viewBox: `${-topViewSize / 2} ${-topViewSize / 2} ${topViewSize} ${topViewSize}`,
    top: {
      fuselage: {
        x: -halfLength,
        y: -fuselageDiameter / 2,
        width: fuselageLength,
        height: fuselageDiameter,
        radius: fuselageDiameter / 2,
      },
      wing: polygon([
        [wingX - rootChord / 2, -0.24],
        [wingX + rootChord / 2, -0.24],
        [wingX + tipChord / 2, -halfSpan],
        [wingX - tipChord / 2, -halfSpan],
        [wingX - tipChord / 2, halfSpan],
        [wingX + tipChord / 2, halfSpan],
        [wingX + rootChord / 2, 0.24],
        [wingX - rootChord / 2, 0.24],
      ]),
      tail: polygon([
        [tailX - rootChord * 0.18, -tailSpan / 2],
        [tailX + rootChord * 0.18, -tailSpan / 2],
        [tailX + rootChord * 0.22, tailSpan / 2],
        [tailX - rootChord * 0.22, tailSpan / 2],
      ]),
      engines:
        engineCount >= 2
          ? [
              { cx: engineX, cy: -engineY, r: engineRadius },
              { cx: engineX, cy: engineY, r: engineRadius },
            ]
          : [],
    },
    side: {
      fuselage: {
        x: -halfLength,
        y: -fuselageDiameter / 2,
        width: fuselageLength,
        height: fuselageDiameter,
        radius: fuselageDiameter / 2,
      },
      wing: polygon([
        [wingX - rootChord / 2, -z],
        [wingX + rootChord / 2, -z],
        [wingX + rootChord * 0.24, -z - 0.12],
        [wingX - rootChord * 0.24, -z - 0.12],
      ]),
      tail: polygon([
        [tailX - rootChord * 0.28, -fuselageDiameter * 0.34],
        [tailX + rootChord * 0.14, -fuselageDiameter * 0.34],
        [tailX + rootChord * 0.18, -fuselageDiameter * 0.95],
        [tailX - rootChord * 0.12, -fuselageDiameter * 0.95],
      ]),
      engines:
        engineCount >= 2
          ? [{ cx: engineX, cy: -(z - fuselageDiameter * 0.25), r: engineRadius }]
          : [],
      wingZ: z,
    },
  };
}
