import assert from "node:assert/strict";
import test from "node:test";

import { resolveGenerationJob, pollJobToCompletion } from "./generationFlow.ts";

// ---------------------------------------------------------------------------
// resolveGenerationJob
// ---------------------------------------------------------------------------

test("resolveGenerationJob throws when jobId is empty", async () => {
  await assert.rejects(
    () => resolveGenerationJob({ apiBaseUrl: "http://api.test", jobId: "" }),
    /缺少 job_id/,
  );
});

// ---------------------------------------------------------------------------
// pollJobToCompletion
// ---------------------------------------------------------------------------

test("pollJobToCompletion skips polling when initialStatus is succeeded", async () => {
  const result = await pollJobToCompletion({
    apiBaseUrl: "http://api.test",
    jobId: "job-1",
    initialStatus: "succeeded",
    design_id: "demo",
    version_no: 3,
    files: { vsp3: "/tmp/a.vsp3", glb: "/tmp/a.glb" },
  });

  assert.equal(result.status, "succeeded");
  assert.equal(result.design_id, "demo");
  assert.equal(result.version_no, 3);
  assert.deepEqual(result.files, ["vsp3", "glb"]);
});

test("pollJobToCompletion skips polling when initialStatus is succeeded without files", async () => {
  const result = await pollJobToCompletion({
    apiBaseUrl: "http://api.test",
    jobId: "job-1",
    initialStatus: "succeeded",
    design_id: "demo",
    version_no: 1,
  });

  assert.equal(result.status, "succeeded");
  assert.equal(result.files, undefined);
});

test("pollJobToCompletion passes error_message through when already succeeded", async () => {
  const result = await pollJobToCompletion({
    apiBaseUrl: "http://api.test",
    jobId: "job-1",
    initialStatus: "succeeded",
    design_id: "demo",
    version_no: 1,
    error_message: null,
  });

  assert.equal(result.error_message, null);
});

test("pollJobToCompletion throws when jobId is empty", async () => {
  await assert.rejects(
    () =>
      pollJobToCompletion({
        apiBaseUrl: "http://api.test",
        jobId: "",
        initialStatus: "queued",
      }),
    /缺少 job_id/,
  );
});

test("pollJobToCompletion throws when jobId is empty even with succeeded status", async () => {
  await assert.rejects(
    () =>
      pollJobToCompletion({
        apiBaseUrl: "http://api.test",
        jobId: "",
        initialStatus: "succeeded",
      }),
    /缺少 job_id/,
  );
});

// pollJobToCompletion with non-succeeded initialStatus delegates to resolveGenerationJob
// which calls waitForGenerationJob. Since we can't inject fetchFn into resolveGenerationJob,
// we verify the integration by testing pollJobToCompletion with "queued" status.
// This will attempt real HTTP calls, so we test the error path (empty jobId) and
// the succeeded skip-path instead. The full polling integration is covered by
// jobPolling.test.ts.

test("pollJobToCompletion with queued status delegates to polling (integration smoke)", async () => {
  await assert.rejects(
    () =>
      pollJobToCompletion({
        apiBaseUrl: "http://127.0.0.1:1",
        jobId: "job-integration",
        initialStatus: "queued",
      }),
    // Connection refused — confirms it tried to poll
    /ECONNREFUSED|fetch failed|Job API/,
  );
});
