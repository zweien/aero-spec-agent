"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  PARAM_SECTION_LABELS as SECTION_LABELS,
  paramDisplayValue,
  paramFieldLabel,
} from "./parameterLabels";
import type { Scalar } from "./parameterValueTypes";

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
  isApplying?: boolean;
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
        const label = paramFieldLabel(fieldKey);
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

  useEffect(() => {
    if (editing) return;
    draftRef.current = String(scalar.value);
    committedRef.current = scalar.value;
  }, [editing, scalar.value]);

  const stageDraft = useCallback(
    (draft: string) => {
      draftRef.current = draft;
      const newValue =
        typeof scalar.value === "number" ? Number(draft) : draft;

      if (typeof newValue === "number" && Number.isNaN(newValue)) return;
      if (newValue === committedRef.current) return;

      committedRef.current = newValue;
      onCommit(newValue);
    },
    [scalar.value, onCommit],
  );

  const commit = useCallback(() => {
    stageDraft(draftRef.current);
    setEditing(false);
  }, [stageDraft]);

  if (!editing) {
    return (
      <strong
        className="editable-value"
        onClick={() => {
          draftRef.current = String(committedRef.current);
          setEditing(true);
        }}
        title="点击编辑"
      >
        {paramDisplayValue(scalar)}
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
        stageDraft(e.target.value);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          commit();
        } else if (e.key === "Escape") {
          draftRef.current = String(committedRef.current);
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
  isApplying = false,
}: ParameterPanelProps) {
  const parameters = spec ? extractParameters(spec) : [];
  const [collapsed, setCollapsed] = useState(false);

  if (parameters.length === 0) {
    return (
      <section className="panel parameter-panel parameter-panel-empty">
        <p className="parameter-empty-hint">
          生成或加载设计后，可在此查看并编辑全部设计参数。
          <br />
          <small>也可以直接在对话中用自然语言修改（例如「把翼展增加到 14 米」）。</small>
        </p>
      </section>
    );
  }

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
                {paramDisplayValue(item.scalar)}
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
          className={`apply-changes-btn ${pendingCount > 0 ? "apply-changes-pending" : ""} ${
            isApplying ? "apply-changes-applying" : ""
          }`}
          disabled={pendingCount === 0 || isApplying}
          onClick={onApplyChanges}
        >
          {isApplying
            ? "正在应用..."
            : pendingCount > 0
              ? `确认修改 (${pendingCount})`
              : "确认修改"}
        </button>
      )}
    </section>
  );
}
