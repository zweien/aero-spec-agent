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
      className={`toolbar-button add-to-compare${isAdded ? " add-to-compare-added" : ""}`}
      onClick={onAdd}
      disabled={isDisabled}
      title={title}
    >
      {label}
    </button>
  );
}
