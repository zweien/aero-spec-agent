"use client";

import type { DesignRuleEntry, PerformanceEstimateEntry, VspaeroAnalysisEntry } from "@/app/page";

type VersionResponse = {
  files: string[];
  validation_report?: {
    spec_echo?: Record<string, unknown>;
    design_rules?: {
      rules: DesignRuleEntry[];
      summary: Record<string, number>;
    };
    performance_estimate?: {
      estimates: PerformanceEstimateEntry[];
      summary: Record<string, number>;
    };
    vspaero_analysis?: VspaeroAnalysisEntry;
  };
};

type VersionCompareProps = {
  v1No: number;
  v2No: number;
  data: [VersionResponse, VersionResponse];
};

const SPEC_COMPARE_FIELDS = [
  { path: "wing.span", label: "翼展" },
  { path: "wing.root_chord", label: "翼根弦长" },
  { path: "wing.tip_chord", label: "翼尖弦长" },
  { path: "wing.sweep", label: "后掠角" },
  { path: "wing.dihedral", label: "上反角" },
  { path: "wing.position", label: "机翼位置", text: true },
  { path: "wing.airfoil", label: "翼型", text: true },
  { path: "fuselage.length", label: "机长" },
  { path: "fuselage.max_diameter", label: "机身直径" },
  { path: "engine.count", label: "发动机数" },
  { path: "engine.position", label: "发动机位置", text: true },
  { path: "tail.type", label: "尾翼类型", text: true },
  { path: "mission.cruise_speed", label: "巡航速度" },
  { path: "mission.payload", label: "载荷" },
  { path: "mission.priority", label: "优先级", text: true },
];

function _getNestedValue(obj: Record<string, unknown>, path: string): unknown {
  const keys = path.split(".");
  let current: unknown = obj;
  for (const key of keys) {
    if (current == null || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[key];
  }
  return current;
}

function _extractScalar(obj: Record<string, unknown>, path: string): { value: number | string | null; unit: string } {
  const raw = _getNestedValue(obj, path);
  if (raw == null) return { value: null, unit: "" };
  if (typeof raw === "string") return { value: raw, unit: "" };
  if (typeof raw === "number") return { value: raw, unit: "" };
  if (typeof raw === "object") {
    const r = raw as Record<string, unknown>;
    return {
      value: r.value as number ?? null,
      unit: (r.unit as string) ?? "",
    };
  }
  return { value: null, unit: "" };
}

function _formatVal(val: number | string | null, unit: string): string {
  if (val == null) return "—";
  if (typeof val === "string") return val;
  if (Number.isInteger(val)) return `${val}${unit ? " " + unit : ""}`;
  return `${val.toFixed(2)}${unit ? " " + unit : ""}`;
}

function DeltaIndicator({ v1, v2, unit }: { v1: number | null; v2: number | null; unit: string }) {
  if (v1 == null || v2 == null) return <span className="delta-same">—</span>;
  const diff = v2 - v1;
  if (Math.abs(diff) < 1e-9) return <span className="delta-same">—</span>;
  const formatted = Number.isInteger(diff) ? `${Math.abs(diff)}` : `${Math.abs(diff).toFixed(2)}`;
  if (diff > 0) return <span className="delta-up">↑ {formatted}{unit ? " " + unit : ""}</span>;
  return <span className="delta-down">↓ {formatted}{unit ? " " + unit : ""}</span>;
}

export function VersionCompare({ v1No, v2No, data }: VersionCompareProps) {
  const [d1, d2] = data;
  const spec1 = (d1.validation_report?.spec_echo ?? {}) as Record<string, unknown>;
  const spec2 = (d2.validation_report?.spec_echo ?? {}) as Record<string, unknown>;
  const rules1 = d1.validation_report?.design_rules?.rules ?? [];
  const rules2 = d2.validation_report?.design_rules?.rules ?? [];
  const perf1 = d1.validation_report?.performance_estimate?.estimates ?? [];
  const perf2 = d2.validation_report?.performance_estimate?.estimates ?? [];
  const aero1 = d1.validation_report?.vspaero_analysis;
  const aero2 = d2.validation_report?.vspaero_analysis;

  return (
    <div className="version-compare">
      <SpecCompare spec1={spec1} spec2={spec2} v1No={v1No} v2No={v2No} />
      {rules1.length > 0 && rules2.length > 0 && (
        <RulesCompare rules1={rules1} rules2={rules2} v1No={v1No} v2No={v2No} />
      )}
      {perf1.length > 0 && perf2.length > 0 && (
        <PerfCompare perf1={perf1} perf2={perf2} v1No={v1No} v2No={v2No} />
      )}
      {aero1 && aero2 && aero1.status === "success" && aero2.status === "success" && (
        <AeroCompare aero1={aero1} aero2={aero2} v1No={v1No} v2No={v2No} />
      )}
    </div>
  );
}

function SpecCompare({ spec1, spec2, v1No, v2No }: {
  spec1: Record<string, unknown>;
  spec2: Record<string, unknown>;
  v1No: number;
  v2No: number;
}) {
  const rows = SPEC_COMPARE_FIELDS
    .map((f) => {
      const s1 = _extractScalar(spec1, f.path);
      const s2 = _extractScalar(spec2, f.path);
      const isText = "text" in f && f.text;
      return { ...f, s1, s2, isText };
    })
    .filter((r) => r.s1.value != null || r.s2.value != null);

  if (rows.length === 0) return null;

  return (
    <div className="compare-section">
      <div className="compare-section-title">参数对比</div>
      <table className="compare-table">
        <thead>
          <tr>
            <th>参数</th>
            <th>v{v1No}</th>
            <th>v{v2No}</th>
            <th>变化</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.path}>
              <td className="compare-label">{r.label}</td>
              <td>{_formatVal(r.s1.value, r.s1.unit)}</td>
              <td>{_formatVal(r.s2.value, r.s2.unit)}</td>
              <td>
                {r.isText ? (
                  <span className={r.s1.value !== r.s2.value ? "delta-up" : "delta-same"}>
                    {r.s1.value === r.s2.value ? "—" : "已变更"}
                  </span>
                ) : (
                  <DeltaIndicator
                    v1={r.s1.value as number | null}
                    v2={r.s2.value as number | null}
                    unit={r.s1.unit || r.s2.unit}
                  />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const STATUS_ORDER: Record<string, number> = { pass: 0, skip: 1, warn: 2, fail: 3 };

function RulesCompare({ rules1, rules2, v1No, v2No }: {
  rules1: DesignRuleEntry[];
  rules2: DesignRuleEntry[];
  v1No: number;
  v2No: number;
}) {
  const r2Map = new Map(rules2.map((r) => [r.rule_id, r]));
  const rows = rules1
    .map((r1) => {
      const r2 = r2Map.get(r1.rule_id);
      if (!r2) return null;
      const improved = STATUS_ORDER[r2.status] < STATUS_ORDER[r1.status];
      const worsened = STATUS_ORDER[r2.status] > STATUS_ORDER[r1.status];
      return { r1, r2, improved, worsened };
    })
    .filter((x): x is NonNullable<typeof x> => x != null);

  if (rows.length === 0) return null;

  return (
    <div className="compare-section">
      <div className="compare-section-title">设计检查</div>
      <table className="compare-table">
        <thead>
          <tr>
            <th>规则</th>
            <th>v{v1No}</th>
            <th>v{v2No}</th>
            <th>变化</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ r1, r2, improved, worsened }) => (
            <tr key={r1.rule_id}>
              <td className="compare-label">{r1.label}</td>
              <td>
                <span className={`compare-status compare-status-${r1.status}`}>
                  {STATUS_ICON[r1.status]} {r1.status}
                </span>
              </td>
              <td>
                <span className={`compare-status compare-status-${r2.status}`}>
                  {STATUS_ICON[r2.status]} {r2.status}
                </span>
              </td>
              <td>
                {improved && <span className="delta-up">↑ 改善</span>}
                {worsened && <span className="delta-down">↓ 恶化</span>}
                {!improved && !worsened && <span className="delta-same">—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const STATUS_ICON: Record<string, string> = { pass: "✓", warn: "⚠", fail: "✗", skip: "—" };

function PerfCompare({ perf1, perf2, v1No, v2No }: {
  perf1: PerformanceEstimateEntry[];
  perf2: PerformanceEstimateEntry[];
  v1No: number;
  v2No: number;
}) {
  const p2Map = new Map(perf2.map((p) => [p.estimate_id, p]));
  const rows = perf1
    .map((p1) => {
      const p2 = p2Map.get(p1.estimate_id);
      if (!p2) return null;
      return { p1, p2 };
    })
    .filter((x): x is NonNullable<typeof x> => x != null);

  if (rows.length === 0) return null;

  return (
    <div className="compare-section">
      <div className="compare-section-title">性能估算</div>
      <table className="compare-table">
        <thead>
          <tr>
            <th>指标</th>
            <th>v{v1No}</th>
            <th>v{v2No}</th>
            <th>变化</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ p1, p2 }) => (
            <tr key={p1.estimate_id}>
              <td className="compare-label">{p1.label}</td>
              <td>{formatPerfVal(p1)}</td>
              <td>{formatPerfVal(p2)}</td>
              <td>
                <DeltaIndicator v1={p1.value} v2={p2.value} unit={p1.unit || p2.unit} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatPerfVal(e: PerformanceEstimateEntry): string {
  const v = Number.isInteger(e.value) ? `${e.value}` : e.value.toFixed(2);
  return `${v}${e.unit ? " " + e.unit : ""}`;
}

function AeroCompare({ aero1, aero2, v1No, v2No }: {
  aero1: VspaeroAnalysisEntry;
  aero2: VspaeroAnalysisEntry;
  v1No: number;
  v2No: number;
}) {
  const metrics: Array<{ label: string; v1: number | null | undefined; v2: number | null | undefined; unit: string; digits: number }> = [
    { label: "L/D max", v1: aero1.optimal_ld, v2: aero2.optimal_ld, unit: "", digits: 1 },
    { label: "CL opt", v1: aero1.optimal_cl, v2: aero2.optimal_cl, unit: "", digits: 3 },
    { label: "α opt", v1: aero1.optimal_alpha, v2: aero2.optimal_alpha, unit: "°", digits: 1 },
    { label: "CD₀", v1: aero1.cd0_estimate, v2: aero2.cd0_estimate, unit: "", digits: 4 },
    { label: "CL_α", v1: aero1.cl_alpha, v2: aero2.cl_alpha, unit: "/rad", digits: 3 },
  ].filter((m) => m.v1 != null && m.v2 != null);

  if (metrics.length === 0) return null;

  return (
    <div className="compare-section">
      <div className="compare-section-title">气动分析</div>
      <table className="compare-table">
        <thead>
          <tr>
            <th>指标</th>
            <th>v{v1No}</th>
            <th>v{v2No}</th>
            <th>变化</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((m) => (
            <tr key={m.label}>
              <td className="compare-label">{m.label}</td>
              <td>{(m.v1 as number).toFixed(m.digits)}{m.unit}</td>
              <td>{(m.v2 as number).toFixed(m.digits)}{m.unit}</td>
              <td>
                <DeltaIndicator v1={m.v1 as number} v2={m.v2 as number} unit={m.unit} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
