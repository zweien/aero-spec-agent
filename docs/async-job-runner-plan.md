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

Status: implemented for the HTTP generation endpoints, parameter PATCH, and chat-triggered generation. The synchronous `JobRunner.generate(...)` path remains available for unit tests and narrow internal callers.

Use FastAPI `BackgroundTasks` as the first migration step.

Completed:

1. `JobRecord` models `queued`, `running`, `succeeded`, and `failed`.
2. `JobRunner.enqueue_generate(...)` creates the job before generation starts.
3. `JobRunner.run_queued_job(...)` runs the existing CAD generation boundary after enqueue.
4. Job state and error messages are persisted in `storage/jobs/{job_id}.json`.
5. `GET /api/jobs/{job_id}` supports frontend polling.
6. `POST /api/designs/{design_id}/generate` returns `202 Accepted` with `job_id` and job metadata.
7. `PATCH /api/designs/{design_id}/spec` returns `202 Accepted` with `job_id` and job metadata.
8. `/api/chat` receives FastAPI `BackgroundTasks`; `generate_design`, `modify_design`, and `modify_selected_part` emit `generation_started` with `job_id` when running through the async path.
9. The web client polls `GET /api/jobs/{job_id}` for chat generation, selected-part modification, design modification, and parameter panel PATCH.
10. The synchronous `JobRunner.generate(...)` path remains available for deterministic unit tests and direct internal callers.

Failure rule: a failed background job may leave diagnostic files, but it must not make the failed version appear as the current usable version.

Current failure isolation:

- `VersionStore.list_versions(...)` only returns version directories that contain `validation_report.json`.
- A failed job can be queried through `GET /api/jobs/{job_id}` with `status="failed"` and `error_message`.
- The frontend waits for `succeeded` before loading a version, so failed jobs are surfaced as errors instead of replacing the previous usable version.

Remaining Phase 1 hardening:

- Add a small concurrent generation test that proves version numbers remain distinct under overlapping requests.
- Add an explicit diagnostic-version convention if failed version directories need to be shown in a separate UI later.
- Add structured job timestamps (`created_at`, `started_at`, `finished_at`) before introducing external queues.

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

Covered:

- Fake backend success job reaches `succeeded` and creates expected artifacts.
- `/api/chat` emits `generation_started` with `job_id` for `generate_design`, `modify_design`, and `modify_selected_part`; each job is queryable through `/api/jobs/{job_id}`.
- `/api/designs/{design_id}/generate` returns `202` with `job_id` and a pollable job.
- `/api/designs/{design_id}/spec` returns `202` with `job_id` and a pollable job for the new version.
- Fake backend failure records `failed` and keeps the previous version as the only usable listed version.
- Frontend polling handles `succeeded` and `failed` in unit tests.

Still useful:

- `OPENVSP_ERROR_POLICY=fail` route-level regression test with an adapter error stack.
- Concurrent requests allocate distinct version numbers under load.
- Browser-level QA for the full chat `generation_started -> polling -> loadVersion` path.

## Next Agent Focus

Do not return to selected-part basics unless a regression appears. The next useful work is:

- Async task consistency across new endpoints and UI actions.
- Failed job diagnostics and version status metadata.
- Frontend polling QA for every path that can create a version.
- Concurrency protection around version allocation.
