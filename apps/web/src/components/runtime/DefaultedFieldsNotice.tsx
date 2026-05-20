"use client";

import { type JSX, useState } from "react";

export type DefaultedField = {
  path: string;
  label: string;
  value: number | string;
  unit?: string;
  reason: string;
};

export type DefaultedFieldsNoticeProps = {
  fields: DefaultedField[];
};

export function DefaultedFieldsNotice({ fields }: DefaultedFieldsNoticeProps): JSX.Element | null {
  const [open, setOpen] = useState(false);

  if (fields.length === 0) return null;

  return (
    <div style={{
      border: "1px solid var(--border-info, #3b82f6)",
      borderRadius: "6px",
      padding: "8px 12px",
      marginTop: "8px",
      background: "rgba(59, 130, 246, 0.04)",
    }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          background: "none",
          border: "none",
          cursor: "pointer",
          fontSize: "12px",
          color: "var(--text-muted)",
          padding: 0,
          display: "flex",
          alignItems: "center",
          gap: "4px",
          width: "100%",
          textAlign: "left",
        }}
      >
        <span style={{ color: "var(--border-info, #3b82f6)", fontSize: "12px" }}>ℹ</span>
        系统已补全 {fields.length} 个必要参数
        <span style={{ fontSize: "10px", marginLeft: "auto" }}>{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div style={{ marginTop: "8px" }}>
          <p style={{ fontSize: "11px", color: "var(--text-muted)", margin: "0 0 6px 0" }}>
            以下参数由系统根据规则自动补全，用于保证方案可生成。后续可以在参数面板中修改。
          </p>
          <table style={{ width: "100%", fontSize: "12px", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border-default)" }}>
                <th style={{ textAlign: "left", padding: "2px 8px 2px 0", fontWeight: 600, color: "var(--text-muted)" }}>参数</th>
                <th style={{ textAlign: "left", padding: "2px 8px 2px 0", fontWeight: 600, color: "var(--text-muted)" }}>默认值</th>
                <th style={{ textAlign: "left", padding: "2px 0", fontWeight: 600, color: "var(--text-muted)" }}>原因</th>
              </tr>
            </thead>
            <tbody>
              {fields.map((f) => (
                <tr key={f.path} style={{ borderBottom: "1px solid var(--border-default)" }}>
                  <td style={{ padding: "3px 8px 3px 0" }}>{f.label}</td>
                  <td style={{ padding: "3px 8px 3px 0" }}>{String(f.value)}{f.unit ? ` ${f.unit}` : ""}</td>
                  <td style={{ padding: "3px 0", color: "var(--text-muted)" }}>{f.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
