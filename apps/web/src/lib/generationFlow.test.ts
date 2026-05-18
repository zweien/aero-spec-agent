import assert from "node:assert/strict";
import test from "node:test";

import {
  resolveGenerationJob,
  pollJobToCompletion,
} from "./generationFlow.ts";
import type { WaitForJobFn } from "./generationFlow.ts";
import type { JobPollResult } from "../types/job.ts";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fakeWaitForJob(resolved: JobPollResult): WaitForJobFn {
  return async () => resolved;
}

function fakeWaitForJobThatThrows(message: string): WaitForJobFn {
  return async () => {
    throw new Error(message);
  };
}

// ---------------------------------------------------------------------------
// resolveGenerationJob
// ---------------------------------------------------------------------------

test("resolveGenerationJob throws when jobId is empty", async () => {
  await assert.rejects(
    () => resolveGenerationJob({ apiBaseUrl: "http://api.test", jobId: "" }),
    /缺少 job_id/,
  );
});

test("resolveGenerationJob delegates to waitForJob", async () => {
  const expected: JobPollResult = {
    id: "job-1",
    status: "succeeded",
    design_id: "demo",
    version_no: 3,
    files: ["vsp3", "glb"],
  };

  const result = await resolveGenerationJob({
    apiBaseUrl: "http://api.test",
    jobId: "job-1",
    waitForJob: fakeWaitForJob(expected),
  });

  assert.equal(result.status, "succeeded");
  assert.equal(result.design_id, "demo");
  assert.equal(result.version_no, 3);
  assert.deepEqual(result.files, ["vsp3", "glb"]);
});

test("resolveGenerationJob propagates waitForJob errors", async () => {
  await assert.rejects(
    () =>
      resolveGenerationJob({
        apiBaseUrl: "http://api.test",
        jobId: "job-1",
        waitForJob: fakeWaitForJobThatThrows("cad generation failed"),
      }),
    /cad generation failed/,
  );
});

test("resolveGenerationJob passes correct apiBaseUrl and jobId", async () => {
  const calls: Array<{ apiBaseUrl: string; jobId: string }> = [];
  const tracker: WaitForJobFn = async (opts) => {
    calls.push({ apiBaseUrl: opts.apiBaseUrl, jobId: opts.jobId });
    return { id: opts.jobId, status: "succeeded" };
  };

  await resolveGenerationJob({
    apiBaseUrl: "http://custom-api",
    jobId: "my-job-42",
    waitForJob: tracker,
  });

  assert.equal(calls.length, 1);
  assert.equal(calls[0].apiBaseUrl, "http://custom-api");
  assert.equal(calls[0].jobId, "my-job-42");
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

test("pollJobToCompletion polls when status is queued and returns succeeded result", async () => {
  const waited: JobPollResult = {
    id: "job-1",
    status: "succeeded",
    design_id: "demo",
    version_no: 2,
    files: ["vsp3", "glb", "step"],
  };

  const result = await pollJobToCompletion({
    apiBaseUrl: "http://api.test",
    jobId: "job-1",
    initialStatus: "queued",
    waitForJob: fakeWaitForJob(waited),
  });

  assert.equal(result.status, "succeeded");
  assert.equal(result.design_id, "demo");
  assert.equal(result.version_no, 2);
  assert.deepEqual(result.files, ["vsp3", "glb", "step"]);
});

test("pollJobToCompletion polls when status is running", async () => {
  const waited: JobPollResult = {
    id: "job-1",
    status: "succeeded",
    design_id: "demo",
    version_no: 5,
  };

  const result = await pollJobToCompletion({
    apiBaseUrl: "http://api.test",
    jobId: "job-1",
    initialStatus: "running",
    waitForJob: fakeWaitForJob(waited),
  });

  assert.equal(result.status, "succeeded");
  assert.equal(result.version_no, 5);
});

test("pollJobToCompletion propagates failed job error from waitForJob", async () => {
  await assert.rejects(
    () =>
      pollJobToCompletion({
        apiBaseUrl: "http://api.test",
        jobId: "job-1",
        initialStatus: "queued",
        waitForJob: fakeWaitForJobThatThrows("cad backend crashed"),
      }),
    /cad backend crashed/,
  );
});
