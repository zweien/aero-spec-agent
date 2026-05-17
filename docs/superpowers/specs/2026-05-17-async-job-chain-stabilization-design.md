# Async Job Chain Stabilization Design

## Goal

Stabilize the BackgroundTasks-based CAD generation path by locking the current behavior with API integration tests and updating the implementation notes for the async job runner.

## Scope

This design keeps the existing Phase 1 architecture. It does not introduce Celery, Redis, new queues, or a new version metadata model.

## Architecture

FastAPI routes enqueue generation through `JobRunner.enqueue_generate()` and schedule `JobRunner.run_queued_job()` through `BackgroundTasks`. Chat responses emit `generation_started` with a `job_id`; the web client polls `GET /api/jobs/{job_id}` until the job reaches `succeeded` or `failed`, then loads the generated version only on success.

Failed jobs may leave diagnostic files in their allocated version directory, but they are not usable versions because `VersionStore.list_versions()` only returns versions with a generated `validation_report.json`.

## Required Coverage

- `/api/chat` passes `BackgroundTasks` into `ChatService` and emits `generation_started` with a `job_id`.
- `/api/designs/{design_id}/generate` returns `202` with a queued job and exposes final job state through `GET /api/jobs/{job_id}`.
- `/api/designs/{design_id}/spec` returns `202` with a queued job and exposes final job state through `GET /api/jobs/{job_id}`.
- A failing backend produces a `failed` job and does not add that version to the usable version list.
- Documentation clearly marks Phase 1 completed pieces and remaining work.

## Testing Strategy

Use API-level tests with `TestClient`, isolated temporary storage, and `FakeCadBackend` or a small failing backend. Avoid browser-level testing for this pass because frontend polling has dedicated unit tests and the current risk is server contract drift.
