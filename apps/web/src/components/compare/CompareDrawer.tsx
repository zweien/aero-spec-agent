"use client";

import { type JSX, type KeyboardEvent, useCallback, useEffect, useRef } from "react";
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

const FOCUSABLE_SELECTOR = [
  "button:not(:disabled)",
  "[href]",
  "input:not(:disabled)",
  "select:not(:disabled)",
  "textarea:not(:disabled)",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

export function CompareDrawer({
  open,
  items,
  onClose,
  onRemove,
  onClear,
  onViewModel,
  onSetCurrent,
}: CompareDrawerProps): JSX.Element | null {
  const drawerRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

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

  useEffect(() => {
    if (!open) return;

    const previousFocus = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    closeButtonRef.current?.focus();

    return () => {
      previousFocus?.focus();
    };
  }, [open]);

  const handleDrawerKeyDown = useCallback((event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      onClose();
      return;
    }

    if (event.key !== "Tab") return;

    const focusableElements = drawerRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
    if (!focusableElements?.length) {
      event.preventDefault();
      drawerRef.current?.focus();
      return;
    }

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];
    if (event.shiftKey && document.activeElement === firstElement) {
      event.preventDefault();
      lastElement.focus();
    } else if (!event.shiftKey && document.activeElement === lastElement) {
      event.preventDefault();
      firstElement.focus();
    }
  }, [onClose]);

  if (!open) return null;

  const hasMinItems = items.length >= 2;

  return (
    <div className="compare-drawer-scrim">
      <div
        ref={drawerRef}
        className="compare-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="compare-drawer-title"
        tabIndex={-1}
        onKeyDown={handleDrawerKeyDown}
      >
        {/* Header */}
        <div className="compare-drawer-header">
          <div className="compare-drawer-title-row">
            <span id="compare-drawer-title" className="compare-drawer-title">方案对比</span>
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
              ref={closeButtonRef}
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
