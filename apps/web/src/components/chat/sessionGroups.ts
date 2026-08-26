import type { SessionItem } from "./SessionSidebar";

export type SessionGroup = {
  key: string;
  label: string;
  items: SessionItem[];
};

const GROUP_LABELS: Array<{ key: string; label: string; maxAgeDays: number }> = [
  { key: "today", label: "今天", maxAgeDays: 1 },
  { key: "week", label: "最近 7 天", maxAgeDays: 7 },
  { key: "month", label: "最近 30 天", maxAgeDays: 30 },
  { key: "older", label: "更早", maxAgeDays: Infinity },
];

export function sessionDisplayTitle(item: SessionItem): string {
  const title = (item.title ?? "").trim();
  return title || "未命名会话";
}

function ageInDays(item: SessionItem, now: number): number {
  const updated = new Date(item.updated_at).getTime();
  if (!Number.isFinite(updated)) return Infinity;
  return (now - updated) / 86_400_000;
}

// Group sessions into 今天 / 最近 7 天 / 最近 30 天 / 更早 buckets. Buckets
// cascade (an item only appears in the youngest bucket it falls into); empty
// groups are dropped. Items keep their original (newest-first) order.
export function groupSessions(
  items: SessionItem[],
  now: number = Date.now(),
): SessionGroup[] {
  const groups: SessionGroup[] = [];
  let remaining = items;
  for (const bucket of GROUP_LABELS) {
    const matched = remaining.filter(
      (item) => ageInDays(item, now) < bucket.maxAgeDays,
    );
    if (matched.length > 0) {
      groups.push({ key: bucket.key, label: bucket.label, items: matched });
      remaining = remaining.filter((item) => !matched.includes(item));
    }
  }
  return groups;
}

export function filterSessions(items: SessionItem[], query: string): SessionItem[] {
  const q = query.trim().toLowerCase();
  if (!q) return items;
  return items.filter((item) =>
    sessionDisplayTitle(item).toLowerCase().includes(q),
  );
}
