"use client";

import { useCallback, useRef, useState } from "react";

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
  onParameterChange?: (path: string, value: string | number) => void;
  onApplyChanges?: () => void;
  pendingCount?: number;
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

const SLIDER_RANGES: Record<string, { min: number; max: number; step: number }> = {
  cruise_speed: { min: 30, max: 500, step: 10 },
  payload: { min: 0.5, max: 200, step: 1 },
  length: { min: 1, max: 20, step: 0.5 },
  max_diameter: { min: 0.15, max: 3, step: 0.05 },
  span: { min: 2, max: 30, step: 0.5 },
  root_chord: { min: 0.2, max: 5, step: 0.1 },
  tip_chord: { min: 0.1, max: 3, step: 0.1 },
  sweep: { min: 0, max: 45, step: 1 },
  dihedral: { min: -10, max: 15, step: 0.5 },
  count: { min: 1, max: 4, step: 1 },
};

function isScalar(val: unknown): val is Scalar {
  return (
    typeof val === "object" &&
    val !== null &&
    "value" in val &&
    "source" in val
  );
}

type ParamEntry = { label: string; path: string; scalar: Scalar; fieldKey: string };

function extractParameters(
  spec: AircraftSpecData
): ParamEntry[] {
  const params: ParamEntry[] = [];
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
          path: `${sectionKey}.${fieldKey}.value`,
          scalar: fieldValue,
          fieldKey,
        });
      }
    }
  }
  return params;
}

function EditableValue({
  scalar,
  onCommit,
}: {
  scalar: Scalar;
  onCommit: (newValue: string | number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const draftRef = useRef(String(scalar.value));
  const committedRef = useRef(scalar.value);

  const commit = useCallback(() => {
    const draft = draftRef.current;
    const newValue =
      typeof scalar.value === "number" ? Number(draft) : draft;
    if (
      newValue !== committedRef.current &&
      !(typeof newValue === "number" && Number.isNaN(newValue))
    ) {
      committedRef.current = newValue;
      onCommit(newValue);
    }
    setEditing(false);
  }, [scalar.value, onCommit]);

  if (!editing) {
    return (
      <strong
        className="editable-value"
        onClick={() => {
          draftRef.current = String(committedRef.current);
          setEditing(true);
        }}
      >
        {scalar.value}
        {scalar.unit ? ` ${scalar.unit}` : ""}
      </strong>
    );
  }

  return (
    <input
      className="editable-input"
      type={typeof scalar.value === "number" ? "number" : "text"}
      defaultValue={String(scalar.value)}
      autoFocus
      step={typeof scalar.value === "number" ? "any" : undefined}
      onChange={(e) => {
        draftRef.current = e.target.value;
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          commit();
        } else if (e.key === "Escape") {
          setEditing(false);
        }
      }}
      onBlur={commit}
    />
  );
}

function ParamSlider({
  fieldKey,
  scalar,
  onCommit,
}: {
  fieldKey: string;
  scalar: Scalar;
  onCommit: (newValue: number) => void;
}) {
  const range = SLIDER_RANGES[fieldKey];
  if (!range || typeof scalar.value !== "number") return null;

  return (
    <input
      type="range"
      className="param-slider"
      min={range.min}
      max={range.max}
      step={range.step}
      value={scalar.value}
      onChange={(e) => onCommit(Number(e.target.value))}
    />
  );
}

export function ParameterPanel({
  spec,
  onParameterChange,
  onApplyChanges,
  pendingCount = 0,
}: ParameterPanelProps) {
  const parameters = spec ? extractParameters(spec) : [];
  const [collapsed, setCollapsed] = useState(false);

  if (parameters.length === 0) return null;

  return (
    <section
      className={`panel parameter-panel ${collapsed ? "parameter-collapsed" : ""}`}
    >
      <header
        className="parameter-toggle"
        onClick={() => setCollapsed(!collapsed)}
      >
        <span>参数</span>
        <span className="parameter-chevron">
          {collapsed ? "▸" : "▾"}
        </span>
        {!collapsed && (
          <span className="parameter-count">{parameters.length}</span>
        )}
      </header>
      {!collapsed &&
        parameters.map((item) => (
          <div className="parameter-row" key={item.path}>
            <span>{item.label}</span>
            {onParameterChange ? (
              <EditableValue
                scalar={item.scalar}
                onCommit={(v) => onParameterChange(item.path, v)}
              />
            ) : (
              <strong>
                {item.scalar.value}
                {item.scalar.unit ? ` ${item.scalar.unit}` : ""}
              </strong>
            )}
            <small>
              <span
                className={`source-badge source-badge-${item.scalar.source}`}
              >
                {SOURCE_LABELS[item.scalar.source] ?? item.scalar.source}
              </span>{" "}
              {Math.round(item.scalar.confidence * 100)}%
            </small>
            {onParameterChange && (
              <ParamSlider
                fieldKey={item.fieldKey}
                scalar={item.scalar}
                onCommit={(v) => onParameterChange(item.path, v)}
              />
            )}
          </div>
        ))}
      {onApplyChanges && (
        <button
          type="button"
          className={`apply-changes-btn ${pendingCount > 0 ? "apply-changes-pending" : ""}`}
          disabled={pendingCount === 0}
          onClick={onApplyChanges}
        >
          {pendingCount > 0 ? `确认修改 (${pendingCount})` : "确认修改"}
        </button>
      )}
    </section>
  );
}
