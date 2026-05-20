import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { getStepLabel } from "./useJobEventStream.ts";

describe("useJobEventStream", () => {
  describe("getStepLabel", () => {
    it("maps known steps to Chinese labels", () => {
      assert.equal(getStepLabel("writing_spec"), "编写设计规格");
      assert.equal(getStepLabel("geometry_building"), "构建几何模型");
      assert.equal(getStepLabel("mesh_export"), "导出三维模型");
      assert.equal(getStepLabel("report_generating"), "生成分析报告");
      assert.equal(getStepLabel("generating_cad"), "生成 CAD 模型");
      assert.equal(getStepLabel("succeeded"), "设计完成");
      assert.equal(getStepLabel("failed"), "生成失败");
    });

    it("passes through unknown steps", () => {
      assert.equal(getStepLabel("unknown_step"), "unknown_step");
    });
  });
});
