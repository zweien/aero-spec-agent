"use client";

import { useCallback, useState } from "react";
import type { CompareItem } from "./types";

const MAX_COMPARE_ITEMS = 5;

export function useCompareItems() {
  const [items, setItems] = useState<CompareItem[]>([]);

  const addCompareItem = useCallback((item: CompareItem) => {
    setItems((prev) => {
      if (prev.some((i) => i.id === item.id)) return prev;
      if (prev.length >= MAX_COMPARE_ITEMS) return prev;
      return [...prev, item];
    });
  }, []);

  const removeCompareItem = useCallback((id: string) => {
    setItems((prev) => prev.filter((i) => i.id !== id));
  }, []);

  const clearCompareItems = useCallback(() => {
    setItems([]);
  }, []);

  const isInCompare = useCallback(
    (id: string) => items.some((i) => i.id === id),
    [items],
  );

  const updateCompareItem = useCallback((id: string, updates: Partial<CompareItem>) => {
    setItems((prev) =>
      prev.map((i) => (i.id === id ? { ...i, ...updates } : i)),
    );
  }, []);

  return {
    items,
    addCompareItem,
    removeCompareItem,
    clearCompareItems,
    isInCompare,
    updateCompareItem,
    maxItems: MAX_COMPARE_ITEMS,
  };
}
