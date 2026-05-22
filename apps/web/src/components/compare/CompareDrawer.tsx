"use client";

import { type JSX, useCallback } from "react";
import type { CompareItem } from "./types";
import { CompareItemCard } from "./CompareItemCard";
import { CompareTable } from "./CompareTable";
import { exportCompareReport, getExportFilename } from "./exportCompareReport";

export type CompareDrawerProps = {
  open: boolean;
  items: CompareItem[];
  onClose: () => void;
  onRemove: (id: string) => void;
  onClear: () => void;
  onViewModel?: (item: CompareItem) => void;
  onSetCurrent?: (item: CompareItem) => void;
};

export function CompareDrawer({
  open,
  items,
  onClose,
  onRemove,
  onClear,
  onViewModel,
  onSetCurrent,
}: CompareDrawerProps): JSX.Element | null {
  if (!open) return null;

  const hasMinItems = items.length >= 2;

  const handleExport = useCallback(() => {
    const md = exportCompareReport(items);
    if (!md) return;
    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = getExportFilename();
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [items]);

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        bottom: 0,
        width: "min(960px, 94vw)",
        background: "#fff",
        borderLeft: "1px solid var(--border-default)",
        boxShadow: "-4px 0 24px rgba(0,0,0,0.08)",
        zIndex: 1000,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 16px",
          borderBottom: "1px solid var(--border-default)",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 15, fontWeight: 700, color: "var(--text)" }}>
            方案对比
          </span>
          <span
            style={{
              fontSize: 11,
              color: "var(--text-muted)",
              background: "var(--bg-surface)",
              borderRadius: 8,
              padding: "1px 8px",
              border: "1px solid var(--border-default)",
            }}
          >
            {items.length} 个方案
          </span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button
            onClick={handleExport}
            disabled={!hasMinItems}
            style={{
              fontSize: 11,
              padding: "4px 10px",
              background: hasMinItems ? "var(--bg-surface)" : "transparent",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-sm)",
              color: hasMinItems ? "var(--text)" : "var(--text-muted)",
              cursor: hasMinItems ? "pointer" : "not-allowed",
              opacity: hasMinItems ? 1 : 0.5,
            }}
          >
            导出对比报告
          </button>
          {items.length > 0 && (
            <button
              onClick={onClear}
              style={{
                fontSize: 11,
                padding: "4px 10px",
                background: "transparent",
                border: "1px solid var(--border-default)",
                borderRadius: "var(--radius-sm)",
                color: "var(--text-muted)",
                cursor: "pointer",
              }}
            >
              清空对比
            </button>
          )}
          <button
            onClick={onClose}
            style={{
              fontSize: 16,
              padding: "2px 6px",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: "var(--text-muted)",
            }}
          >
            &times;
          </button>
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
        {items.length === 0 ? (
          <EmptyState
            title="还没有加入对比的方案"
            subtitle="可在版本历史或 Deep Design 方案卡片中点击「加入对比」"
          />
        ) : !hasMinItems ? (
          <EmptyState
            title="请至少加入 2 个方案进行对比"
            subtitle="在版本历史或 Deep Design 方案中点击「加入对比」"
          />
        ) : (
          <>
            {/* Disclaimer notice */}
            <div
              style={{
                fontSize: 11,
                color: "var(--text-muted)",
                background: "rgba(59,130,246,0.04)",
                border: "1px solid rgba(59,130,246,0.12)",
                borderRadius: 6,
                padding: "8px 12px",
                marginBottom: 12,
                lineHeight: 1.5,
              }}
            >
              当前指标为概念设计阶段估算，用于方案初筛，不代表高保真气动或结构分析结果。
            </div>

            {/* Defaulted fields trust notice */}
            {items.some((i) => (i.defaultedFields?.length ?? 0) >= 3) && (
              <div
                style={{
                  fontSize: 11,
                  color: "var(--warning, #ca8a04)",
                  background: "rgba(234,179,8,0.06)",
                  border: "1px solid rgba(234,179,8,0.2)",
                  borderRadius: 6,
                  padding: "8px 12px",
                  marginBottom: 12,
                  lineHeight: 1.5,
                }}
              >
                部分方案包含较多系统默认补全参数，默认补全越多说明由系统假设的内容越多。建议在进入工程分析前进一步确认参数。
              </div>
            )}

            {/* Item cards row — scrollable when many */}
            <div
              style={{
                display: "flex",
                gap: 8,
                marginBottom: 16,
                overflowX: "auto",
                paddingBottom: 4,
              }}
            >
              {items.map((item) => (
                <div key={item.id} style={{ minWidth: 150, flex: "1 0 150px" }}>
                  <CompareItemCard
                    item={item}
                    onRemove={onRemove}
                    onViewModel={onViewModel}
                    onSetCurrent={onSetCurrent}
                  />
                </div>
              ))}
            </div>

            {/* Compare table */}
            <CompareTable items={items} />
          </>
        )}
      </div>
    </div>
  );
}

function EmptyState({ title, subtitle }: { title: string; subtitle: string }): JSX.Element {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: 200,
        color: "var(--text-muted)",
        gap: 8,
      }}
    >
      <span style={{ fontSize: 14, fontWeight: 500 }}>{title}</span>
      <span style={{ fontSize: 12 }}>{subtitle}</span>
    </div>
  );
}
