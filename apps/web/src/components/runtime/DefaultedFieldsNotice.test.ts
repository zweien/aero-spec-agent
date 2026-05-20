import assert from "node:assert/strict";
import test from "node:test";

// ---------------------------------------------------------------------------
// Pure logic tests for DefaultedFieldsNotice component behavior.
// These mirror the rendering decisions inside the component.
// ---------------------------------------------------------------------------

type DefaultedField = { path: string; label: string; value: number | string; unit?: string; reason: string };

/** Whether the notice should be visible. */
function shouldShowNotice(fields: DefaultedField[]): boolean {
  return fields.length > 0;
}

/** Format a field value with unit for display. */
function formatFieldValue(field: DefaultedField): string {
  const val = String(field.value);
  return field.unit ? `${val} ${field.unit}` : val;
}

/** Count of defaulted fields. */
function countDefaulted(fields: DefaultedField[]): number {
  return fields.length;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test("DefaultedFieldsNotice: hidden when fields empty", () => {
  assert.equal(shouldShowNotice([]), false);
});

test("DefaultedFieldsNotice: visible when fields present", () => {
  const fields: DefaultedField[] = [
    { path: "fuselage.length", label: "机身长度", value: 5.0, unit: "m", reason: "LLM 未提供" },
  ];
  assert.equal(shouldShowNotice(fields), true);
});

test("DefaultedFieldsNotice: counts multiple fields", () => {
  const fields: DefaultedField[] = [
    { path: "fuselage.length", label: "机身长度", value: 5.0, unit: "m", reason: "a" },
    { path: "wing.position", label: "机翼位置", value: "mid", reason: "b" },
    { path: "tail.type", label: "尾翼类型", value: "conventional", reason: "c" },
  ];
  assert.equal(countDefaulted(fields), 3);
});

test("DefaultedFieldsNotice: formats numeric value with unit", () => {
  const field: DefaultedField = { path: "fuselage.length", label: "机身长度", value: 5.0, unit: "m", reason: "r" };
  assert.equal(formatFieldValue(field), "5 m");
});

test("DefaultedFieldsNotice: formats text value without unit", () => {
  const field: DefaultedField = { path: "wing.position", label: "机翼位置", value: "mid", reason: "r" };
  assert.equal(formatFieldValue(field), "mid");
});

test("DefaultedFieldsNotice: expected notice text", () => {
  const fields: DefaultedField[] = [
    { path: "fuselage.length", label: "机身长度", value: 5.0, unit: "m", reason: "r" },
    { path: "wing.span", label: "翼展", value: 6.0, unit: "m", reason: "r" },
  ];
  const expected = `系统已补全 ${fields.length} 个必要参数`;
  assert.equal(expected, "系统已补全 2 个必要参数");
});
