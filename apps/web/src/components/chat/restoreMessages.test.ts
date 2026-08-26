import assert from "node:assert/strict";
import test from "node:test";

import { restoreMessages } from "./restoreMessages.ts";

const generateResult = {
  job_id: "job-1",
  status: "succeeded",
  design_id: "d-1",
  version_no: 4,
  files: ["aircraft.vsp3", "aircraft.glb"],
};

const history = [
  { role: "user", content: "设计一架翼展6米的无人机" },
  {
    role: "assistant",
    content: null,
    tool_calls: [
      {
        id: "call-1",
        type: "function",
        function: {
          name: "generate_design",
          arguments: '{"span": 6}',
        },
      },
    ],
  },
  {
    role: "tool",
    tool_call_id: "call-1",
    content: JSON.stringify(generateResult),
  },
  {
    role: "assistant",
    content: "设计完成，翼展 6 米。",
  },
  { role: "user", content: "把翼展改成 8 米" },
  {
    role: "assistant",
    content: null,
    tool_calls: [
      {
        id: "call-2",
        type: "function",
        function: {
          name: "modify_design",
          arguments: '{"changes": []}',
        },
      },
    ],
  },
  {
    role: "tool",
    tool_call_id: "call-2",
    content: JSON.stringify({
      job_id: "job-2",
      status: "failed",
      design_id: "d-1",
      error_message: "cad failed",
    }),
  },
  { role: "assistant", content: "修改失败了。" },
];

test("restoreMessages rebuilds tool cards with job output", () => {
  const { messages } = restoreMessages(history as never[]);

  assert.equal(messages.length, 4);
  const runBubble = messages[1];
  assert.equal(runBubble.role, "assistant");

  const toolPart = runBubble.parts.find((p) => p.type === "tool");
  assert.ok(toolPart, "tool part should be restored");
  assert.equal(toolPart.type === "tool" && toolPart.toolName, "generate_design");
  assert.equal(
    toolPart.type === "tool" && (toolPart.output as Record<string, unknown>)?.version_no,
    4,
  );
  assert.equal(toolPart.type === "tool" && toolPart.state, "done");
  const text = runBubble.parts
    .filter((p) => p.type === "text")
    .map((p) => (p.type === "text" ? p.text : ""))
    .join("");
  assert.match(text, /设计完成/);
});

test("restoreMessages marks failed runs via runtimeError", () => {
  const { messages } = restoreMessages(history as never[]);
  const failedBubble = messages[3];
  const toolPart = failedBubble.parts.find((p) => p.type === "tool");
  assert.ok(toolPart && toolPart.type === "tool");
  assert.equal(toolPart.runtimeError, "cad failed");
});

test("restoreMessages keeps plain messages as text-only bubbles", () => {
  const { messages } = restoreMessages([
    { role: "user", content: "你好" },
    { role: "assistant", content: "你好，有什么可以帮你？" },
  ] as never[]);
  assert.equal(messages.length, 2);
  assert.equal(messages[0].parts.length, 1);
  assert.equal(messages[1].parts[0].type, "text");
});

test("restoreMessages tolerates malformed tool payloads", () => {
  const { messages } = restoreMessages([
    { role: "user", content: "hi" },
    {
      role: "assistant",
      tool_calls: [{ id: "c1", function: { name: "generate_design", arguments: "{bad json" } }],
    },
    { role: "tool", tool_call_id: "c1", content: "not json at all" },
  ] as never[]);
  const bubble = messages[1];
  const toolPart = bubble.parts.find((p) => p.type === "tool");
  assert.ok(toolPart && toolPart.type === "tool");
  assert.equal(toolPart.output, undefined);
  assert.equal(toolPart.toolName, "generate_design");
});
