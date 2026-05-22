"use client";

import { type JSX } from "react";

export type AddToCompareButtonProps = {
  isAdded: boolean;
  onAdd: () => void;
  disabled?: boolean;
  maxReached?: boolean;
};

export function AddToCompareButton({ isAdded, onAdd, disabled, maxReached }: AddToCompareButtonProps): JSX.Element {
  const isDisabled = disabled || isAdded || maxReached;
  const label = isAdded ? "已加入" : maxReached ? "对比已满" : "加入对比";
  const title = maxReached ? "最多支持 5 个方案同时对比" : undefined;

  return (
    <button
      onClick={onAdd}
      disabled={isDisabled}
      title={title}
      style={{
        fontSize: 11,
        padding: "4px 8px",
        background: isAdded ? "var(--bg-surface)" : "transparent",
        border: isAdded ? "1px solid var(--success)" : "1px solid var(--border-default)",
        borderRadius: "var(--radius-sm)",
        color: isAdded ? "var(--success)" : isDisabled ? "var(--text-muted)" : "var(--text-dim)",
        cursor: isDisabled ? "default" : "pointer",
        opacity: isDisabled && !isAdded ? 0.5 : 1,
      }}
    >
      {label}
    </button>
  );
}
