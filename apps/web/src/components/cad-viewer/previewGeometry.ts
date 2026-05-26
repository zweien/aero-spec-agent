type Scalar = {
  value: string | number;
  unit?: string | null;
};

export const LAYOUT_LABELS: Record<string, string> = {
  conventional: "常规布局",
  twin_boom: "双尾撑",
  flying_wing: "飞翼",
  blended_wing_body: "翼身融合",
  canard: "鸭翼布局",
  three_surface: "三翼面",
  tandem_wing: "串列翼",
  biplane: "双翼机",
  joined_wing: "连接翼",
  box_wing: "箱式翼",
  multi_fuselage: "双机身",
};

export function extractLayout(spec: AircraftPreviewSpec | null): string {
  if (!spec) return "conventional";
  const aircraftObj = (spec as Record<string, unknown>).aircraft as Record<string, unknown> | undefined;
  const rawLayout = spec.layout ?? aircraftObj?.layout;
  const layoutStr = typeof rawLayout === "string" ? rawLayout : (rawLayout as Scalar | null | undefined)?.value;
  return typeof layoutStr === "string" && layoutStr.trim()
    ? layoutStr.trim().toLowerCase()
    : "conventional";
}

export type AircraftPreviewSpec = {
  layout?: Scalar | null;
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
  canard?: {
    span: Scalar;
    chord: Scalar;
    sweep?: Scalar | null;
    x_position_ratio?: Scalar | null;
  } | null;
  rear_wing?: {
    span: Scalar;
    chord: Scalar;
    sweep?: Scalar | null;
    x_position_ratio?: Scalar | null;
    gap?: Scalar | null;
  } | null;
  second_wing?: {
    span: Scalar;
    chord: Scalar;
    sweep?: Scalar | null;
    dihedral?: Scalar | null;
    gap: Scalar;
    stagger?: Scalar | null;
  } | null;
  boom?: {
    length: Scalar;
    span: Scalar;
  } | null;
  body?: {
    width: Scalar;
    height: Scalar;
  } | null;
  multi_fuselage?: {
    spacing: Scalar;
    fuselage_count?: Scalar | null;
  } | null;
  box_wing_config?: {
    gap: Scalar;
    endplate_chord?: Scalar | null;
  } | null;
};

type Circle = {
  cx: number;
  cy: number;
  r: number;
};

export type PreviewElement = {
  kind: "polygon" | "rect" | "circle";
  className: string;
  points?: string;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  radius?: number;
  cx?: number;
  cy?: number;
  r?: number;
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
  sideViewBox: string;
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
    underlays: PreviewElement[];
    overlays: PreviewElement[];
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
    underlays: PreviewElement[];
    overlays: PreviewElement[];
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

// ── Layout element generators ──────────────────────────────────────

function canardElements(
  spec: AircraftPreviewSpec,
  fuselageLength: number,
  fuselageDiameter: number,
  wingSpan: number,
  rootChord: number,
): { top: PreviewElement[]; side: PreviewElement[] } {
  if (!spec.canard) return { top: [], side: [] };
  const span = numberValue(spec.canard.span, wingSpan * 0.35);
  const chord = numberValue(spec.canard.chord, rootChord * 0.6);
  const xRatio = numberValue(spec.canard.x_position_ratio, 0.15);
  const canardX = -fuselageLength / 2 + fuselageLength * xRatio;
  const halfSpan = span / 2;
  const tipChord = chord * 0.7;

  return {
    top: [{
      kind: "polygon",
      className: "preview-canard",
      points: polygon([
        [canardX - chord / 2, -0.18],
        [canardX + chord / 2, -0.18],
        [canardX + tipChord / 2, -halfSpan],
        [canardX - tipChord / 2, -halfSpan],
        [canardX - tipChord / 2, halfSpan],
        [canardX + tipChord / 2, halfSpan],
        [canardX + chord / 2, 0.18],
        [canardX - chord / 2, 0.18],
      ]),
    }],
    side: [{
      kind: "polygon",
      className: "preview-canard",
      points: polygon([
        [canardX - chord / 2, -fuselageDiameter * 0.34],
        [canardX + chord / 2, -fuselageDiameter * 0.34],
        [canardX + chord * 0.24, -fuselageDiameter * 0.65],
        [canardX - chord * 0.24, -fuselageDiameter * 0.65],
      ]),
    }],
  };
}

function rearWingElements(
  spec: AircraftPreviewSpec,
  fuselageLength: number,
  fuselageDiameter: number,
  wingSpan: number,
  rootChord: number,
  z: number,
  isJoined: boolean,
): { top: PreviewElement[]; side: PreviewElement[] } {
  if (!spec.rear_wing) return { top: [], side: [] };
  const span = numberValue(spec.rear_wing.span, wingSpan * 0.7);
  const chord = numberValue(spec.rear_wing.chord, rootChord * 0.8);
  const xRatio = numberValue(spec.rear_wing.x_position_ratio, isJoined ? 0.70 : 0.65);
  const rearX = fuselageLength * xRatio - fuselageLength / 2;
  const halfSpan = span / 2;
  const tipChord = isJoined ? chord * 0.6 : chord * 0.8;
  const sweep = numberValue(spec.rear_wing.sweep, isJoined ? -15 : 0);
  const sweepOffset = halfSpan * Math.tan((sweep * Math.PI) / 180);

  return {
    top: [{
      kind: "polygon",
      className: "preview-rear-wing",
      points: polygon([
        [rearX - chord / 2, -0.18],
        [rearX + chord / 2, -0.18],
        [rearX + tipChord / 2 + sweepOffset, -halfSpan],
        [rearX - tipChord / 2 + sweepOffset, -halfSpan],
        [rearX - tipChord / 2 - sweepOffset, halfSpan],
        [rearX + tipChord / 2 - sweepOffset, halfSpan],
        [rearX + chord / 2, 0.18],
        [rearX - chord / 2, 0.18],
      ]),
    }],
    side: [{
      kind: "polygon",
      className: "preview-rear-wing",
      points: polygon([
        [rearX - chord / 2, -z],
        [rearX + chord / 2, -z],
        [rearX + chord * 0.24, -z - 0.12],
        [rearX - chord * 0.24, -z - 0.12],
      ]),
    }],
  };
}

function secondWingElements(
  spec: AircraftPreviewSpec,
  wingX: number,
  wingSpan: number,
  rootChord: number,
  z: number,
): { top: PreviewElement[]; side: PreviewElement[] } {
  if (!spec.second_wing) return { top: [], side: [] };
  const span = numberValue(spec.second_wing.span, wingSpan * 0.85);
  const chord = numberValue(spec.second_wing.chord, rootChord * 0.8);
  const gap = numberValue(spec.second_wing.gap, 1.0);
  const stagger = numberValue(spec.second_wing.stagger, 0.3);
  const halfSpan = span / 2;
  const tipChord = chord * 0.8;
  const lowerX = wingX + stagger;

  return {
    top: [{
      kind: "polygon",
      className: "preview-lower-wing",
      points: polygon([
        [lowerX - chord / 2, -0.18],
        [lowerX + chord / 2, -0.18],
        [lowerX + tipChord / 2, -halfSpan],
        [lowerX - tipChord / 2, -halfSpan],
        [lowerX - tipChord / 2, halfSpan],
        [lowerX + tipChord / 2, halfSpan],
        [lowerX + chord / 2, 0.18],
        [lowerX - chord / 2, 0.18],
      ]),
    }],
    side: [{
      kind: "polygon",
      className: "preview-lower-wing",
      points: polygon([
        [lowerX - chord / 2, -(z + gap)],
        [lowerX + chord / 2, -(z + gap)],
        [lowerX + chord * 0.24, -(z + gap) - 0.12],
        [lowerX - chord * 0.24, -(z + gap) - 0.12],
      ]),
    }],
  };
}

function boxWingElements(
  spec: AircraftPreviewSpec,
  wingX: number,
  wingSpan: number,
  rootChord: number,
  z: number,
): { top: PreviewElement[]; side: PreviewElement[] } {
  if (!spec.box_wing_config) return { top: [], side: [] };
  const gap = numberValue(spec.box_wing_config.gap, 1.5);
  const halfSpan = wingSpan / 2;
  const lowerChord = rootChord * 0.6;
  const endplateChord = numberValue(spec.box_wing_config.endplate_chord, 0.3);
  const lowerZ = z + gap;

  return {
    top: [
      {
        kind: "polygon",
        className: "preview-lower-wing",
        points: polygon([
          [wingX - rootChord / 2, -0.18],
          [wingX + rootChord / 2, -0.18],
          [wingX + lowerChord / 2, -halfSpan],
          [wingX - lowerChord / 2, -halfSpan],
          [wingX - lowerChord / 2, halfSpan],
          [wingX + lowerChord / 2, halfSpan],
          [wingX + rootChord / 2, 0.18],
          [wingX - rootChord / 2, 0.18],
        ]),
      },
      {
        kind: "polygon",
        className: "preview-endplate",
        points: polygon([
          [wingX - endplateChord / 2, -halfSpan - 0.04],
          [wingX + endplateChord / 2, -halfSpan - 0.04],
          [wingX + endplateChord / 2, -halfSpan + 0.04],
          [wingX - endplateChord / 2, -halfSpan + 0.04],
        ]),
      },
      {
        kind: "polygon",
        className: "preview-endplate",
        points: polygon([
          [wingX - endplateChord / 2, halfSpan - 0.04],
          [wingX + endplateChord / 2, halfSpan - 0.04],
          [wingX + endplateChord / 2, halfSpan + 0.04],
          [wingX - endplateChord / 2, halfSpan + 0.04],
        ]),
      },
    ],
    side: [
      {
        kind: "polygon",
        className: "preview-lower-wing",
        points: polygon([
          [wingX - rootChord / 2, -lowerZ],
          [wingX + rootChord / 2, -lowerZ],
          [wingX + rootChord * 0.24, -lowerZ - 0.12],
          [wingX - rootChord * 0.24, -lowerZ - 0.12],
        ]),
      },
      {
        kind: "polygon",
        className: "preview-endplate",
        points: polygon([
          [wingX - endplateChord / 2, -z],
          [wingX + endplateChord / 2, -z],
          [wingX + endplateChord / 2, -lowerZ],
          [wingX - endplateChord / 2, -lowerZ],
        ]),
      },
    ],
  };
}

function boomElements(
  spec: AircraftPreviewSpec,
  fuselageLength: number,
  fuselageDiameter: number,
  wingSpan: number,
): { top: PreviewElement[]; side: PreviewElement[] } {
  if (!spec.boom) return { top: [], side: [] };
  const boomLength = numberValue(spec.boom.length, fuselageLength * 0.5);
  const boomSpan = numberValue(spec.boom.span, wingSpan * 0.3);
  const boomDiameter = fuselageDiameter * 0.15;
  const boomBaseX = fuselageLength * 0.40 - fuselageLength / 2;
  const halfBoomSpan = boomSpan / 2;

  return {
    top: [
      {
        kind: "rect",
        className: "preview-boom",
        x: boomBaseX,
        y: -halfBoomSpan - boomDiameter / 2,
        width: boomLength,
        height: boomDiameter,
        radius: boomDiameter / 2,
      },
      {
        kind: "rect",
        className: "preview-boom",
        x: boomBaseX,
        y: halfBoomSpan - boomDiameter / 2,
        width: boomLength,
        height: boomDiameter,
        radius: boomDiameter / 2,
      },
    ],
    side: [
      {
        kind: "rect",
        className: "preview-boom",
        x: boomBaseX,
        y: -boomDiameter / 2,
        width: boomLength,
        height: boomDiameter,
        radius: boomDiameter / 2,
      },
    ],
  };
}

function bwbBodyElements(
  spec: AircraftPreviewSpec,
  fuselageLength: number,
  fuselageDiameter: number,
): { top: PreviewElement[]; side: PreviewElement[] } {
  if (!spec.body) return { top: [], side: [] };
  const width = numberValue(spec.body.width, fuselageDiameter * 3);
  const height = numberValue(spec.body.height, fuselageDiameter * 0.6);
  const halfLength = fuselageLength / 2;

  return {
    top: [{
      kind: "rect",
      className: "preview-bwb-body",
      x: -halfLength,
      y: -width / 2,
      width: fuselageLength,
      height: width,
      radius: width * 0.15,
    }],
    side: [{
      kind: "rect",
      className: "preview-bwb-body",
      x: -halfLength,
      y: -height / 2,
      width: fuselageLength,
      height: height,
      radius: height / 3,
    }],
  };
}

function multiFuselageElements(
  spec: AircraftPreviewSpec,
  fuselageLength: number,
  fuselageDiameter: number,
): { top: PreviewElement[]; side: PreviewElement[] } {
  if (!spec.multi_fuselage) return { top: [], side: [] };
  const spacing = numberValue(spec.multi_fuselage.spacing, fuselageLength * 0.5);
  const halfSpacing = spacing / 2;
  const halfLength = fuselageLength / 2;

  return {
    top: [
      {
        kind: "rect",
        className: "preview-boom",
        x: -halfLength,
        y: -halfSpacing - fuselageDiameter / 2,
        width: fuselageLength,
        height: fuselageDiameter,
        radius: fuselageDiameter / 2,
      },
      {
        kind: "rect",
        className: "preview-boom",
        x: -halfLength,
        y: halfSpacing - fuselageDiameter / 2,
        width: fuselageLength,
        height: fuselageDiameter,
        radius: fuselageDiameter / 2,
      },
    ],
    side: [],
  };
}

// ── Main builder ────────────────────────────────────────────────────

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
  const wingX = -fuselageLength * 0.08;
  const tailX = halfLength * 0.72;
  const tailSpan = wingSpan * 0.28;
  const engineY = wingSpan * 0.25;
  const engineRadius = Math.max(fuselageDiameter * 0.22, 0.12);
  const engineX = wingX + rootChord * 0.25;
  const z = wingZ(position, fuselageDiameter);
  // Layout may be at spec.layout (AircraftPreviewSpec) or spec.aircraft.layout (full spec_echo)
  const aircraftObj = (spec as Record<string, unknown>).aircraft as Record<string, unknown> | undefined;
  const rawLayout = spec.layout ?? aircraftObj?.layout;
  // aircraft.layout may be a Scalar { value: "canard" } or a plain string
  const layoutStr = typeof rawLayout === "string" ? rawLayout : (rawLayout as Scalar | null | undefined)?.value;
  const layout = typeof layoutStr === "string" && layoutStr.trim() ? layoutStr.trim().toLowerCase() : "conventional";

  // Layout dispatch
  let showTail = true;
  const underlays: PreviewElement[] = [];
  const overlays: PreviewElement[] = [];
  const sideUnderlays: PreviewElement[] = [];
  const sideOverlays: PreviewElement[] = [];
  let maxSideExtent = fuselageDiameter * 0.95;

  switch (layout) {
    case "canard":
    case "three_surface": {
      const c = canardElements(spec, fuselageLength, fuselageDiameter, wingSpan, rootChord);
      overlays.push(...c.top);
      sideOverlays.push(...c.side);
      break;
    }
    case "tandem_wing":
    case "joined_wing": {
      showTail = false;
      const rw = rearWingElements(spec, fuselageLength, fuselageDiameter, wingSpan, rootChord, z, layout === "joined_wing");
      overlays.push(...rw.top);
      sideOverlays.push(...rw.side);
      break;
    }
    case "biplane": {
      const sw = secondWingElements(spec, wingX, wingSpan, rootChord, z);
      underlays.push(...sw.top);
      sideUnderlays.push(...sw.side);
      const gap = numberValue(spec.second_wing?.gap, 1.0);
      maxSideExtent = Math.max(maxSideExtent, z + gap + 0.12);
      break;
    }
    case "box_wing": {
      const bw = boxWingElements(spec, wingX, wingSpan, rootChord, z);
      underlays.push(...bw.top);
      sideUnderlays.push(...bw.side);
      const gap = numberValue(spec.box_wing_config?.gap, 1.5);
      maxSideExtent = Math.max(maxSideExtent, z + gap + 0.12);
      break;
    }
    case "twin_boom": {
      const booms = boomElements(spec, fuselageLength, fuselageDiameter, wingSpan);
      underlays.push(...booms.top);
      sideUnderlays.push(...booms.side);
      break;
    }
    case "flying_wing": {
      showTail = false;
      break;
    }
    case "blended_wing_body": {
      showTail = false;
      const bwb = bwbBodyElements(spec, fuselageLength, fuselageDiameter);
      underlays.push(...bwb.top);
      sideUnderlays.push(...bwb.side);
      const bodyHeight = numberValue(spec.body?.height, fuselageDiameter * 0.6);
      maxSideExtent = Math.max(maxSideExtent, bodyHeight / 2);
      break;
    }
    case "multi_fuselage": {
      const mf = multiFuselageElements(spec, fuselageLength, fuselageDiameter);
      underlays.push(...mf.top);
      sideUnderlays.push(...mf.side);
      break;
    }
  }

  // ViewBox calculations
  const topViewSize = Math.max(fuselageLength, wingSpan) + topMargin * 2;
  const sideH = maxSideExtent + 0.5;
  const sideW = Math.max(fuselageLength * 1.1, 8.4);
  const sideViewBox = `${-sideW / 2} ${-sideH - 0.3} ${sideW} ${(sideH + 0.3) * 2}`;

  const tailPolygon = showTail
    ? polygon([
        [tailX - rootChord * 0.18, -tailSpan / 2],
        [tailX + rootChord * 0.18, -tailSpan / 2],
        [tailX + rootChord * 0.22, tailSpan / 2],
        [tailX - rootChord * 0.22, tailSpan / 2],
      ])
    : "";

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
    sideViewBox,
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
      tail: tailPolygon,
      engines:
        engineCount >= 2
          ? [
              { cx: engineX, cy: -engineY, r: engineRadius },
              { cx: engineX, cy: engineY, r: engineRadius },
            ]
          : [],
      underlays,
      overlays,
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
      tail: showTail
        ? polygon([
            [tailX - rootChord * 0.28, -fuselageDiameter * 0.34],
            [tailX + rootChord * 0.14, -fuselageDiameter * 0.34],
            [tailX + rootChord * 0.18, -fuselageDiameter * 0.95],
            [tailX - rootChord * 0.12, -fuselageDiameter * 0.95],
          ])
        : "",
      engines:
        engineCount >= 2
          ? [{ cx: engineX, cy: -(z - fuselageDiameter * 0.25), r: engineRadius }]
          : [],
      wingZ: z,
      underlays: sideUnderlays,
      overlays: sideOverlays,
    },
  };
}
