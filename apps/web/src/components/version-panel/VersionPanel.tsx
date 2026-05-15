import { useState } from "react";

import { buildVersionFileUrl } from "@/components/cad-viewer/cadPreviewSource";
import type { DesignRuleEntry } from "@/app/page";

type VersionPanelProps = {
  apiBaseUrl: string;
  designId: string;
  jobStatus?: string;
  versionNo?: number;
  files: string[];
  designRules?: DesignRuleEntry[] | null;
};

export function VersionPanel({
  apiBaseUrl,
  designId,
  jobStatus,
  versionNo,
  files,
  designRules,
}: VersionPanelProps) {
  const canLinkFiles = versionNo !== undefined;

  return (
    <section className="bottom-panel">
      <span>任务状态：{jobStatus ?? "idle"}</span>
      <span>版本：{versionNo ?? "-"}</span>
      <span className="file-list">
        文件：
        {files.length
          ? files.map((file, index) => (
              <span key={file}>
                {index > 0 ? ", " : ""}
                {canLinkFiles ? (
                  <a
                    href={buildVersionFileUrl(apiBaseUrl, designId, versionNo, file)}
                    rel="noreferrer"
                    target="_blank"
                  >
                    {file}
                  </a>
                ) : (
                  file
                )}
              </span>
            ))
          : "-"}
      </span>
      {designRules && designRules.length > 0 && (
        <DesignRulesSummary rules={designRules} />
      )}
    </section>
  );
}

function DesignRulesSummary({ rules }: { rules: DesignRuleEntry[] }) {
  const [expanded, setExpanded] = useState(false);
  const counts = { pass: 0, warn: 0, fail: 0, skip: 0 };
  for (const r of rules) {
    counts[r.status]++;
  }

  return (
    <span className="design-rules">
      <button
        type="button"
        className="design-rules-toggle"
        onClick={() => setExpanded(!expanded)}
      >
        设计检查
        {counts.fail > 0 && (
          <span className="design-rule-pill design-rule-pill-fail">
            {counts.fail}
          </span>
        )}
        {counts.warn > 0 && (
          <span className="design-rule-pill design-rule-pill-warn">
            {counts.warn}
          </span>
        )}
        {counts.fail === 0 && counts.warn === 0 && (
          <span className="design-rule-pill design-rule-pill-pass">
            {counts.pass}
          </span>
        )}
        <span className="design-rules-arrow">
          {expanded ? "▾" : "▸"}
        </span>
      </button>
      {expanded && (
        <div className="design-rules-list">
          <div className="design-rules-bar">
            <span className="design-rule-pill design-rule-pill-pass">
              通过 {counts.pass}
            </span>
            {counts.warn > 0 && (
              <span className="design-rule-pill design-rule-pill-warn">
                警告 {counts.warn}
              </span>
            )}
            {counts.fail > 0 && (
              <span className="design-rule-pill design-rule-pill-fail">
                失败 {counts.fail}
              </span>
            )}
            {counts.skip > 0 && (
              <span className="design-rule-pill design-rule-pill-skip">
                跳过 {counts.skip}
              </span>
            )}
          </div>
          {rules.map((r) => (
            <div key={r.rule_id} className={`design-rule-row design-rule-${r.status}`}>
              <span className="design-rule-icon">{STATUS_ICON[r.status]}</span>
              <span className="design-rule-label">{r.label}</span>
              <span className="design-rule-value">
                {typeof r.value === "number" ? r.value : r.value}
              </span>
              <span className="design-rule-expected">{r.expected}</span>
              <span className="design-rule-msg">{r.message}</span>
            </div>
          ))}
        </div>
      )}
    </span>
  );
}

const STATUS_ICON: Record<string, string> = {
  pass: "✓",
  warn: "⚠",
  fail: "✗",
  skip: "—",
};
