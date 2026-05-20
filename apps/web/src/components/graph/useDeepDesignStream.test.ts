import assert from "node:assert/strict";
import test from "node:test";

// ---------------------------------------------------------------------------
// parseSseChunk — copied from useDeepDesignStream.ts because that module
// imports from GraphExecutionPanel.tsx which Node --experimental-strip-types
// cannot resolve.  The function under test must stay identical to the source.
// ---------------------------------------------------------------------------

type DeepDesignSseEvent = {
  event: string;
  data: Record<string, unknown>;
};

function parseSseChunk(chunk: string): DeepDesignSseEvent[] {
  const events: DeepDesignSseEvent[] = [];
  let currentEvent: string | null = null;
  let currentData: string | null = null;

  for (const line of chunk.split("\n")) {
    if (line.startsWith("event: ")) {
      currentEvent = line.slice(7);
    } else if (line.startsWith("data: ")) {
      currentData = line.slice(6);
    } else if (line === "" && currentEvent !== null && currentData !== null) {
      try {
        events.push({
          event: currentEvent,
          data: JSON.parse(currentData),
        });
      } catch {
        // Skip malformed JSON
      }
      currentEvent = null;
      currentData = null;
    }
  }
  return events;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test("parseSseChunk parses single event", () => {
  const chunk = "event: graph_node\ndata: {\"node\":\"parse\",\"status\":\"started\"}\n\n";
  const events = parseSseChunk(chunk);
  assert.equal(events.length, 1);
  assert.equal(events[0].event, "graph_node");
  assert.equal(events[0].data.node, "parse");
  assert.equal(events[0].data.status, "started");
});

test("parseSseChunk parses multiple events", () => {
  const chunk =
    "event: graph_node\ndata: {\"node\":\"parse\",\"status\":\"started\"}\n\n" +
    "event: graph_node\ndata: {\"node\":\"parse\",\"status\":\"completed\",\"latency_ms\":5.2}\n\n";
  const events = parseSseChunk(chunk);
  assert.equal(events.length, 2);
  assert.equal(events[1].data.latency_ms, 5.2);
});

test("parseSseChunk handles incomplete chunk", () => {
  const chunk = "event: graph_node\ndata: {\"node\":\"parse\"";
  const events = parseSseChunk(chunk);
  assert.equal(events.length, 0);
});

test("parseSseChunk handles generation_progress", () => {
  const chunk =
    "event: generation_progress\ndata: {\"job_id\":\"abc123\",\"current_step\":\"mesh_export\",\"progress\":40}\n\n";
  const events = parseSseChunk(chunk);
  assert.equal(events.length, 1);
  assert.equal(events[0].event, "generation_progress");
  assert.equal(events[0].data.job_id, "abc123");
});

test("parseSseChunk handles message event", () => {
  const chunk =
    'event: message\ndata: {"content":"Done","status":"completed","design_id":"test-1"}\n\n';
  const events = parseSseChunk(chunk);
  assert.equal(events.length, 1);
  assert.equal(events[0].data.content, "Done");
  assert.equal(events[0].data.status, "completed");
});
