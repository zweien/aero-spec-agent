"use client";

import { type JSX } from "react";

export type AddToCompareButtonProps = {
  isAdded: boolean;
  onAdd: () => void;
  disabled?: boolean;
};

export function AddToCompareButton({ isAdded, onAdd, disabled }: AddToCompareButtonProps): JSX.Element {
  return (
    <button
      onClick={onAdd}
      disabled={disabled || isAdded}
      style={{
        fontSize: 11,
        padding: "4px 8px",
        background: isAdded ? "var(--bg-surface)" : "transparent",
        border: isAdded ? "1px solid var(--success, #16a34a)" : "1px solid var(--border-default)",
        borderRadius: "var(--radius-sm)",
        color: isAdded ? "var(--success, #16a34a)" : disabled ? "var(--text-muted)" : "var(--text-dim)",
        cursor: disabled || isAdded ? "default" : "pointer",
        opacity: disabled && !isAdded ? 0.5 : 1,
      }}
    >
      {isAdded ? "已加入" : "加入对比"}
    </button>
  );
}
