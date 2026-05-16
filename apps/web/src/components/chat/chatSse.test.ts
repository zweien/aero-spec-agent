import assert from "node:assert/strict";
import test from "node:test";

import { createChatSseParser } from "./chatSse.ts";

test("createChatSseParser parses FastAPI chat events across chunks", () => {
  const parser = createChatSseParser();

  const first = parser.push('event: message\ndata: {"content":"hel');
  const second = parser.push(
    'lo"}\n\nevent: tool_call\ndata: {"name":"generate_design","arguments":"{}"}\n\n' +
      'event: generation_started\ndata: {"design_id":"d1"}\n\n' +
      'event: generation_complete\ndata: {"design_id":"d1","version_no":2,"files":["aircraft.glb"]}\n\n' +
      'event: error\ndata: {"content":"bad"}\n\n',
  );

  assert.deepEqual(first, []);
  assert.deepEqual(second, [
    { type: "message", data: { content: "hello" } },
    { type: "tool_call", data: { name: "generate_design", arguments: "{}" } },
    { type: "generation_started", data: { design_id: "d1" } },
    {
      type: "generation_complete",
      data: { design_id: "d1", version_no: 2, files: ["aircraft.glb"] },
    },
    { type: "error", data: { content: "bad" } },
  ]);
});
