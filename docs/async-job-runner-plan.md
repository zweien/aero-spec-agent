# Async JobRunner Migration Plan

## Current State

`JobRunner` runs CAD generation synchronously inside the API request path. It creates the next version directory, writes `aircraft_spec.yaml`, calls the selected CAD backend, then records artifacts, generation logs, and validation reports through `VersionStore`.

This is simple and keeps tests deterministic, but OpenVSP generation can block request handling. The migration should preserve the existing spec-first contract: tools only patch `aircraft_spec`, generation failures must not overwrite older good versions, and `FakeCadBackend` must remain usable for local development and tests.

## Goals

- Keep `VersionStore` as the source of truth for version artifacts.
- Keep `JobRunner` as the narrow orchestration boundary around CAD generation.
- Add asynchronous execution without replacing the chat flow in one step.
- Preserve deterministic fake-backend tests.
- Surface failed jobs explicitly instead of hiding OpenVSP failures.

## Phase 1: In-process BackgroundTasks

Use FastAPI `BackgroundTasks` as the first migration step.

1. Add a `JobRecord` state transition model: `queued`, `running`, `succeeded`, `failed`.
2. Create a job before generation starts and return `202 Accepted` with `job_id`, `design_id`, and the intended version number.
3. Run the existing `JobRunner.generate(...)` in a background task.
4. Persist job status and error messages in a small JSON record next to the design or in a dedicated `storage/jobs/` directory.
5. Add `GET /api/jobs/{job_id}` for polling.
6. Keep the current synchronous path available for tests until the frontend polling path is fully covered.

Failure rule: a failed background job may leave diagnostic files, but it must not make the failed version appear as the current usable version.

## Phase 2: Durable Queue

Move the same job contract to RQ or Celery when in-process tasks are no longer enough.

1. Use Redis as broker/result store.
2. Serialize only stable data into the queue payload: `job_id`, `design_id`, `version_no`, `aircraft_spec` JSON, backend name, and analysis flags.
3. Let workers reconstruct `JobRunner` and backend dependencies from configuration.
4. Keep generated files written by `VersionStore`; do not pass binary artifacts through the queue.
5. Add retry policy only for transient infrastructure failures, not deterministic spec validation errors.

## Phase 3: Robustness

- Add version allocation locking so concurrent jobs cannot claim the same version.
- Add cancellation support for queued jobs.
- Add stale-job recovery for worker crashes.
- Isolate OpenVSP execution per worker process.
- Clean up failed partial artifacts after diagnostics are preserved.
- Add metrics for queue wait time, generation duration, backend error policy, and artifact export failures.

## API Sketch

```text
POST /api/generate
  -> 202 { job_id, design_id, version_no, status: "queued" }

GET /api/jobs/{job_id}
  -> { job_id, design_id, version_no, status, error?, artifacts? }

GET /api/designs/{design_id}/versions/{version_no}
  -> existing version payload once status == "succeeded"
```

## Test Plan

- Fake backend success job reaches `succeeded` and creates expected artifacts.
- Fake backend failure records `failed` and keeps previous version current.
- `OPENVSP_ERROR_POLICY=fail` maps adapter errors to failed jobs.
- Concurrent requests allocate distinct version numbers.
- Frontend polling handles `queued`, `running`, `succeeded`, and `failed` states.
