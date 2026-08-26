import assert from "node:assert/strict";
import test from "node:test";

import {
  paramFieldLabel,
  paramValueLabel,
} from "./../parameter-panel/parameterLabels.ts";
import {
  filterSessions,
  groupSessions,
  sessionDisplayTitle,
} from "./sessionGroups.ts";
import type { SessionItem } from "./SessionSidebar.ts";

test("paramFieldLabel covers previously untranslated keys", () => {
  assert.equal(paramFieldLabel("planform"), "翼平面形状");
  assert.equal(paramFieldLabel("sections"), "截面段数");
  assert.equal(paramFieldLabel("z_rel_location"), "展向位置");
  assert.equal(paramFieldLabel("span"), "翼展");
  // Unknown keys pass through
  assert.equal(paramFieldLabel("custom_field"), "custom_field");
});

test("paramValueLabel translates enum identifiers but keeps airfoils", () => {
  assert.equal(paramValueLabel("rear_fuselage"), "后机身");
  assert.equal(paramValueLabel("v_tail"), "V型尾");
  assert.equal(paramValueLabel("delta"), "三角翼");
  assert.equal(paramValueLabel("endurance"), "长航时");
  assert.equal(paramValueLabel("NACA2412"), "NACA2412");
  assert.equal(paramValueLabel("NACA64A204"), "NACA64A204");
  // Unknown values pass through
  assert.equal(paramValueLabel("some_custom"), "some_custom");
  assert.equal(paramValueLabel(2), "2");
});

function session(id: string, title: string, ageDays: number): SessionItem {
  const now = Date.now();
  return {
    conversation_id: id,
    title,
    created_at: new Date(now - ageDays * 86_400_000).toISOString(),
    updated_at: new Date(now - ageDays * 86_400_000).toISOString(),
    message_count: 1,
    design_id: id,
  };
}

test("sessionDisplayTitle falls back for blank titles", () => {
  const now = Date.now();
  assert.equal(sessionDisplayTitle(session("a", "", 0)), "未命名会话");
  assert.equal(sessionDisplayTitle(session("b", "   ", 0)), "未命名会话");
  assert.equal(
    sessionDisplayTitle(session("c", "设计一架无人机", 0)),
    "设计一架无人机",
  );
});

test("groupSessions buckets by recency and drops empty groups", () => {
  const now = Date.now();
  const items = [
    session("today", "今天的会话", 0.1),
    session("week", "本周会话", 3),
    session("older", "更早会话", 45),
  ];
  const groups = groupSessions(items, now);
  assert.deepEqual(
    groups.map((g) => g.key),
    ["today", "week", "older"],
  );
  assert.equal(groups[0].items[0].conversation_id, "today");
  assert.equal(groups[2].items[0].conversation_id, "older");
});

test("filterSessions matches titles case-insensitively", () => {
  const items = [
    session("a", "设计一架翼展12米无人机", 0),
    session("b", "BWB patrol", 1),
  ];
  assert.equal(filterSessions(items, "翼展").length, 1);
  assert.equal(filterSessions(items, "bwb").length, 1);
  assert.equal(filterSessions(items, "不存在").length, 0);
  assert.equal(filterSessions(items, "").length, 2);
});
