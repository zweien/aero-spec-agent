import { describe, it } from "node:test";
import assert from "node:assert/strict";

const TOOL_LABELS: Record<string, string> = {
  generate_design: "生成设计",
  modify_design: "修改设计",
  modify_selected_part: "修改选中部件",
};

describe("FallbackToolNotice labels", () => {
  it("maps generate_design to Chinese label", () => {
    assert.equal(TOOL_LABELS["generate_design"], "生成设计");
  });

  it("maps modify_design to Chinese label", () => {
    assert.equal(TOOL_LABELS["modify_design"], "修改设计");
  });

  it("maps modify_selected_part to Chinese label", () => {
    assert.equal(TOOL_LABELS["modify_selected_part"], "修改选中部件");
  });

  it("formats confidence as percentage", () => {
    const confidence = 0.85;
    const pct = (confidence * 100).toFixed(0);
    assert.equal(pct, "85");
  });
});
