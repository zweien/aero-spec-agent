import assert from "node:assert/strict";
import test from "node:test";

import {
  parseSseChunk,
  type DeepDesignSseEvent,
} from "./useDeepDesignStream";

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
