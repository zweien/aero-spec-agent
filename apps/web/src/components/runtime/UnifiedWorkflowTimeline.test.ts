import assert from "node:assert/strict";
import test from "node:test";

// ---------------------------------------------------------------------------
// Inline types mirrored from UnifiedWorkflowTimeline.tsx and useWorkflowRuntime.ts
// ---------------------------------------------------------------------------

type GraphNodeState = "pending" | "running" | "completed" | "failed";

type GraphNode = {
  name: string;
  label: string;
  state: GraphNodeState;
  latencyMs?: number;
};

type WorkflowRuntimeStage = {
  stage: string;
  label: string;
  status: "completed" | "running" | "pending" | "failed";
  startedAt: number | null;
  completedAt: number | null;
  durationMs: number | null;
};

// ---------------------------------------------------------------------------
// Conversion function under test — must stay identical to the one in
// UnifiedWorkflowTimeline.tsx.  We copy it here because Node's
// --experimental-strip-types cannot import .tsx modules.
// ---------------------------------------------------------------------------

function nodesToStages(nodes: GraphNode[]): WorkflowRuntimeStage[] {
  return nodes.map((n) => ({
    stage: n.name,
    label: n.label,
    status: n.state as WorkflowRuntimeStage["status"],
    startedAt: null,
    completedAt: null,
    durationMs: n.latencyMs ?? null,
  }));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test("nodesToStages maps name -> stage", () => {
  const nodes: GraphNode[] = [
    { name: "parse_requirements", label: "解析设计目标", state: "completed" },
  ];
  const stages = nodesToStages(nodes);
  assert.equal(stages[0].stage, "parse_requirements");
});

test("nodesToStages maps label -> label", () => {
  const nodes: GraphNode[] = [
    { name: "run_compare", label: "分析方案差异", state: "running" },
  ];
  const stages = nodesToStages(nodes);
  assert.equal(stages[0].label, "分析方案差异");
});

test("nodesToStages maps state -> status for all states", () => {
  const states: Array<GraphNode["state"]> = ["pending", "running", "completed", "failed"];
  for (const s of states) {
    const nodes: GraphNode[] = [{ name: "node", label: "Node", state: s }];
    const stages = nodesToStages(nodes);
    assert.equal(stages[0].status, s);
  }
});

test("nodesToStages maps latencyMs -> durationMs", () => {
  const nodes: GraphNode[] = [
    { name: "node", label: "Node", state: "completed", latencyMs: 42 },
  ];
  const stages = nodesToStages(nodes);
  assert.equal(stages[0].durationMs, 42);
});

test("nodesToStages sets durationMs to null when latencyMs is undefined", () => {
  const nodes: GraphNode[] = [
    { name: "node", label: "Node", state: "pending" },
  ];
  const stages = nodesToStages(nodes);
  assert.equal(stages[0].durationMs, null);
});

test("nodesToStages preserves node ordering", () => {
  const nodes: GraphNode[] = [
    { name: "parse_requirements", label: "解析设计目标", state: "completed" },
    { name: "prepare_variants", label: "生成候选方案", state: "running" },
    { name: "synthesize_report", label: "生成设计建议", state: "pending" },
  ];
  const stages = nodesToStages(nodes);
  assert.equal(stages.length, 3);
  assert.equal(stages[0].stage, "parse_requirements");
  assert.equal(stages[1].stage, "prepare_variants");
  assert.equal(stages[2].stage, "synthesize_report");
});

test("nodesToStages sets startedAt and completedAt to null", () => {
  const nodes: GraphNode[] = [
    { name: "node", label: "Node", state: "completed", latencyMs: 100 },
  ];
  const stages = nodesToStages(nodes);
  assert.equal(stages[0].startedAt, null);
  assert.equal(stages[0].completedAt, null);
});
