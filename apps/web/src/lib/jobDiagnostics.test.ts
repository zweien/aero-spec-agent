import assert from "node:assert/strict";
import test from "node:test";

import { fetchJobDiagnostics } from "./jobDiagnostics.ts";

const SAMPLE_DIAG = {
  job: { id: "abc-123", status: "succeeded" },
  version_status: { status: "succeeded" },
  generation_log: null,
  validation_report: { rules: [] },
  files_exist: { "aircraft.vsp3": true, "aircraft.glb": false },
};

test("fetchJobDiagnostics returns parsed diagnostics on 200", async () => {
  const result = await fetchJobDiagnostics(
    "http://api.test",
    "abc-123",
    async (url) => {
      assert.ok(url.includes("/api/jobs/abc-123/diagnostics"));
      return new Response(JSON.stringify(SAMPLE_DIAG), { status: 200 });
    },
  );

  assert.deepEqual(result, SAMPLE_DIAG);
});

test("fetchJobDiagnostics returns null on 404", async () => {
  const result = await fetchJobDiagnostics(
    "http://api.test",
    "missing",
    async () => new Response("not found", { status: 404 }),
  );

  assert.equal(result, null);
});

test("fetchJobDiagnostics returns null on 500", async () => {
  const result = await fetchJobDiagnostics(
    "http://api.test",
    "err",
    async () => new Response("internal error", { status: 500 }),
  );

  assert.equal(result, null);
});

test("fetchJobDiagnostics returns null on network error", async () => {
  const result = await fetchJobDiagnostics(
    "http://api.test",
    "netfail",
    async () => { throw new Error("ECONNREFUSED"); },
  );

  assert.equal(result, null);
});

test("fetchJobDiagnostics returns null on JSON parse error", async () => {
  const result = await fetchJobDiagnostics(
    "http://api.test",
    "badjson",
    async () => new Response("not json", { status: 200 }),
  );

  assert.equal(result, null);
});

test("fetchJobDiagnostics URL-encodes jobId with special characters", async () => {
  let calledUrl = "";
  await fetchJobDiagnostics(
    "http://api.test",
    "job/with/slashes",
    async (url) => {
      calledUrl = String(url);
      return new Response("{}", { status: 404 });
    },
  );

  assert.ok(calledUrl.includes("job%2Fwith%2Fslashes"));
});
