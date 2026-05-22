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
    <div className="compare-drawer">
      {/* Header */}
      <div className="compare-drawer-header">
        <div className="compare-drawer-title-row">
          <span className="compare-drawer-title">方案对比</span>
          <span className="pill pill-neutral">
            {items.length} 个方案
          </span>
        </div>
        <div className="compare-drawer-actions">
          <button
            className="toolbar-button"
            onClick={handleExport}
            disabled={!hasMinItems}
          >
            导出对比报告
          </button>
          {items.length > 0 && (
            <button
              className="toolbar-button compare-clear-button"
              onClick={onClear}
            >
              清空对比
            </button>
          )}
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="关闭对比"
          >
            &times;
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="compare-drawer-body">
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
            <div className="notice notice-info">
              当前指标为概念设计阶段估算，用于方案初筛，不代表高保真气动或结构分析结果。
            </div>

            {/* Defaulted fields trust notice */}
            {items.some((i) => (i.defaultedFields?.length ?? 0) >= 3) && (
              <div className="notice notice-warning">
                部分方案包含较多系统默认补全参数，默认补全越多说明由系统假设的内容越多。建议在进入工程分析前进一步确认参数。
              </div>
            )}

            {/* Item cards row — scrollable when many */}
            <div className="compare-item-row">
              {items.map((item) => (
                <div key={item.id} className="compare-item-slot">
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
    <div className="compare-empty-state">
      <span className="compare-empty-title">{title}</span>
      <span className="compare-empty-subtitle">{subtitle}</span>
    </div>
  );
}
