import assert from "node:assert/strict";
import test from "node:test";

import { buildAgentRunActions } from "./AgentRunActionsModel.ts";


test("buildAgentRunActions returns all completed actions enabled when handlers are provided", () => {
  const actions = buildAgentRunActions({
    status: "completed",
    onViewModel: () => {},
    onDeepDesign: () => {},
    onExportReport: () => {},
    onShowDetails: () => {},
  });

  assert.deepEqual(
    actions.map((action) => [action.label, action.disabled]),
    [
      ["查看模型", false],
      ["深度设计探索", false],
      ["导出报告", false],
      ["查看运行细节", false],
    ],
  );
});


test("buildAgentRunActions keeps unavailable completed actions visible and disabled", () => {
  const actions = buildAgentRunActions({ status: "completed" });

  assert.deepEqual(
    actions.map((action) => [action.label, action.disabled, action.disabledReason]),
    [
      ["查看模型", true, "模型生成后可用"],
      ["深度设计探索", true, "当前设计加载后可用"],
      ["导出报告", true, "报告生成后可用"],
      ["查看运行细节", true, "运行详情加载后可用"],
    ],
  );
});
