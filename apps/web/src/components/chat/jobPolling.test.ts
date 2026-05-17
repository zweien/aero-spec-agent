import assert from "node:assert/strict";
import test from "node:test";

import { waitForGenerationJob } from "./jobPolling.ts";

test("waitForGenerationJob polls until the job succeeds", async () => {
  const calls: string[] = [];
  const responses = [
    { id: "job-1", status: "running", progress: 50 },
    {
      id: "job-1",
      status: "succeeded",
      progress: 100,
      design_id: "demo",
      version_no: 2,
      files: { vsp3: "/tmp/aircraft.vsp3", glb: "/tmp/aircraft.glb" },
    },
  ];

  const result = await waitForGenerationJob({
    apiBaseUrl: "http://api.test",
    jobId: "job-1",
    intervalMs: 0,
    fetchFn: async (url) => {
      calls.push(String(url));
      const body = responses.shift();
      return new Response(JSON.stringify(body), { status: 200 });
    },
  });

  assert.deepEqual(calls, [
    "http://api.test/api/jobs/job-1",
    "http://api.test/api/jobs/job-1",
  ]);
  assert.equal(result.status, "succeeded");
  assert.equal(result.version_no, 2);
  assert.deepEqual(result.files, ["vsp3", "glb"]);
});

test("waitForGenerationJob throws when the job fails", async () => {
  await assert.rejects(
    () =>
      waitForGenerationJob({
        apiBaseUrl: "http://api.test",
        jobId: "job-1",
        intervalMs: 0,
        fetchFn: async () =>
          new Response(
            JSON.stringify({
              id: "job-1",
              status: "failed",
              error_message: "cad failed",
            }),
            { status: 200 },
          ),
      }),
    /cad failed/,
  );
});
