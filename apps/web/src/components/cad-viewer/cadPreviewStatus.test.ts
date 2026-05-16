import assert from "node:assert/strict";
import test from "node:test";

import {
  cadPreviewStatusLabel,
  type CadPreviewStatus,
} from "./cadPreviewStatus.ts";

test("cadPreviewStatusLabel describes loaded generated models", () => {
  assert.equal(
    cadPreviewStatusLabel({ format: "glb", state: "loaded" }),
    "已加载 GLB 模型",
  );
  assert.equal(
    cadPreviewStatusLabel({ format: "obj", state: "loaded" }),
    "已加载 OBJ 模型",
  );
});

test("cadPreviewStatusLabel describes loading and fallback states", () => {
  const loading: CadPreviewStatus = { format: "glb", state: "loading" };
  const fallback: CadPreviewStatus = { format: "obj", state: "fallback" };

  assert.equal(cadPreviewStatusLabel(loading), "正在加载 GLB 模型");
  assert.equal(cadPreviewStatusLabel(fallback), "参数化 3D 预览");
  assert.equal(cadPreviewStatusLabel({ state: "parameter" }), "参数化 3D 预览");
});
