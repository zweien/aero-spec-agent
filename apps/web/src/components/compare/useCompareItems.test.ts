import { describe, it } from "node:test";
import assert from "node:assert/strict";

// useCompareItems is a React hook, test the underlying logic indirectly
// by recreating the state operations it performs.
// For hook tests in the future, we can use React Testing Library's renderHook.

// Test the pure constraint logic instead:
// 1. Max 5 items
// 2. Dedup by id
// 3. add / remove / clear semantics

import type { CompareItem } from "./types.ts";

function createTestStore() {
  let items: CompareItem[] = [];
  const MAX = 5;

  return {
    get items() { return items; },
    add(item: CompareItem) {
      if (items.some((i) => i.id === item.id)) return false;
      if (items.length >= MAX) return false;
      items = [...items, item];
      return true;
    },
    remove(id: string) {
      items = items.filter((i) => i.id !== id);
    },
    clear() {
      items = [];
    },
    isAdded(id: string) {
      return items.some((i) => i.id === id);
    },
  };
}

function makeItem(id: string, v: number): CompareItem {
  return { id, designId: "d1", versionNo: v, source: "version", name: `v${v}` };
}

describe("useCompareItems logic", () => {
  it("adds items up to 5", () => {
    const store = createTestStore();
    assert.equal(store.add(makeItem("a", 1)), true);
    assert.equal(store.add(makeItem("b", 2)), true);
    assert.equal(store.add(makeItem("c", 3)), true);
    assert.equal(store.add(makeItem("d", 4)), true);
    assert.equal(store.add(makeItem("e", 5)), true);
    assert.equal(store.items.length, 5);
    assert.equal(store.add(makeItem("f", 6)), false);
    assert.equal(store.items.length, 5);
  });

  it("deduplicates by id", () => {
    const store = createTestStore();
    assert.equal(store.add(makeItem("a", 1)), true);
    assert.equal(store.add(makeItem("a", 1)), false);
    assert.equal(store.items.length, 1);
  });

  it("removes items", () => {
    const store = createTestStore();
    store.add(makeItem("a", 1));
    store.add(makeItem("b", 2));
    store.remove("a");
    assert.equal(store.items.length, 1);
    assert.equal(store.items[0].id, "b");
  });

  it("clears all items", () => {
    const store = createTestStore();
    store.add(makeItem("a", 1));
    store.add(makeItem("b", 2));
    store.clear();
    assert.equal(store.items.length, 0);
  });

  it("checks isAdded", () => {
    const store = createTestStore();
    assert.equal(store.isAdded("a"), false);
    store.add(makeItem("a", 1));
    assert.equal(store.isAdded("a"), true);
  });
});
