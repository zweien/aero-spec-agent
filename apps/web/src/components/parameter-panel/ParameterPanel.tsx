"use client";

type Scalar = {
  value: string | number;
  unit?: string;
  source: string;
  confidence: number;
  reason?: string;
};

type SpecSection = {
  [key: string]: Scalar | SpecSection | undefined;
};

export type AircraftSpecData = {
  aircraft?: { name?: string; type?: string; layout?: string };
  mission?: SpecSection;
  fuselage?: SpecSection;
  wing?: SpecSection;
  tail?: SpecSection;
  engine?: SpecSection;
};

type ParameterPanelProps = {
  spec: AircraftSpecData | null;
};

const SECTION_LABELS: Record<string, string> = {
  mission: "任务需求",
  fuselage: "机身",
  wing: "机翼",
  tail: "尾翼",
  engine: "发动机",
};

const FIELD_LABELS: Record<string, string> = {
  cruise_speed: "巡航速度",
  payload: "载荷",
  priority: "优先级",
  length: "长度",
  max_diameter: "最大直径",
  position: "位置",
  span: "翼展",
  root_chord: "根弦长",
  tip_chord: "尖弦长",
  sweep: "后掠角",
  dihedral: "上反角",
  airfoil: "翼型",
  type: "类型",
  count: "数量",
};

const SOURCE_LABELS: Record<string, string> = {
  user: "用户",
  inferred: "推断",
  rule_default: "默认",
  system_default: "系统",
};

function isScalar(val: unknown): val is Scalar {
  return (
    typeof val === "object" &&
    val !== null &&
    "value" in val &&
    "source" in val
  );
}

function extractParameters(
  spec: AircraftSpecData
): Array<{ label: string; scalar: Scalar }> {
  const params: Array<{ label: string; scalar: Scalar }> = [];
  for (const [sectionKey, sectionLabel] of Object.entries(SECTION_LABELS)) {
    const section = spec[sectionKey as keyof AircraftSpecData] as
      | SpecSection
      | undefined;
    if (!section) continue;
    for (const [fieldKey, fieldValue] of Object.entries(section)) {
      if (fieldValue !== undefined && isScalar(fieldValue)) {
        const label = FIELD_LABELS[fieldKey] ?? fieldKey;
        params.push({
          label: `${sectionLabel} · ${label}`,
          scalar: fieldValue,
        });
      }
    }
  }
  return params;
}

export function ParameterPanel({ spec }: ParameterPanelProps) {
  const parameters = spec ? extractParameters(spec) : [];

  return (
    <section className="panel parameter-panel">
      <header>参数</header>
      {parameters.length === 0 ? (
        <div className="parameter-empty">
          等待生成设计参数
        </div>
      ) : (
        parameters.map((item) => (
          <div className="parameter-row" key={item.label}>
            <span>{item.label}</span>
            <strong>
              {item.scalar.value}
              {item.scalar.unit ? ` ${item.scalar.unit}` : ""}
            </strong>
            <small>
              <span className={`source-badge source-badge-${item.scalar.source}`}>
                {SOURCE_LABELS[item.scalar.source] ?? item.scalar.source}
              </span>
              {" "}
              {Math.round(item.scalar.confidence * 100)}%
            </small>
          </div>
        ))
      )}
    </section>
  );
}
