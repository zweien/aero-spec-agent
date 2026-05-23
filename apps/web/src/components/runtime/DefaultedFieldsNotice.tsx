"use client";

import { type JSX, useId, useState } from "react";

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
  const detailsId = useId();

  if (fields.length === 0) return null;

  return (
    <div className="runtime-notice runtime-notice-info">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="runtime-notice-toggle"
        aria-expanded={open}
        aria-controls={detailsId}
      >
        <span className="runtime-notice-icon">ℹ</span>
        系统已补全 {fields.length} 个必要参数
        <span className="runtime-notice-caret">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div id={detailsId} className="runtime-notice-body">
          <p className="runtime-notice-copy">
            以下参数由系统根据规则自动补全，用于保证方案可生成。后续可以在参数面板中修改。
          </p>
          <table className="runtime-notice-table">
            <thead>
              <tr>
                <th scope="col">参数</th>
                <th scope="col">默认值</th>
                <th scope="col">原因</th>
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
