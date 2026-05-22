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
    <div className="runtime-notice runtime-notice-info">
      <button
        onClick={() => setOpen(!open)}
        className="runtime-notice-toggle"
      >
        <span className="runtime-notice-icon">ℹ</span>
        系统已补全 {fields.length} 个必要参数
        <span className="runtime-notice-caret">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="runtime-notice-body">
          <p className="runtime-notice-copy">
            以下参数由系统根据规则自动补全，用于保证方案可生成。后续可以在参数面板中修改。
          </p>
          <table className="runtime-notice-table">
            <thead>
              <tr>
                <th>参数</th>
                <th>默认值</th>
                <th>原因</th>
              </tr>
            </thead>
            <tbody>
              {fields.map((f) => (
                <tr key={f.path}>
                  <td>{f.label}</td>
                  <td>{String(f.value)}{f.unit ? ` ${f.unit}` : ""}</td>
                  <td>{f.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
