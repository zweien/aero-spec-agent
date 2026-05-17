# Async Job Chain Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lock the BackgroundTasks async generation chain with API integration tests and update the async runner documentation.

**Architecture:** Keep the current synchronous `JobRunner.generate()` path for tests and the async `enqueue_generate()` plus `run_queued_job()` path for routes. API tests validate route contracts; documentation records what Phase 1 now supports and what remains.

**Tech Stack:** FastAPI `TestClient`, pytest, temporary `VersionStore`, `FakeCadBackend`, markdown docs.

---

### Task 1: Chat Async Job API Contract

**Files:**
- Modify: `tests/api/test_chat_service.py`

- [ ] **Step 1: Add a fake LLM response that calls `generate_design`**

Use the existing ChatService test patterns to inject an LLM response with a `generate_design` tool call.

- [ ] **Step 2: Add API-level test**

Add a test that posts to `/api/chat`, reads SSE events, asserts a `generation_started` event includes `job_id`, then polls `/api/jobs/{job_id}` and asserts `succeeded`.

- [ ] **Step 3: Run focused tests**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_chat_service.py -q`

Expected: all tests pass.

### Task 2: Design Generate/Patch Job API Contracts

**Files:**
- Modify: `tests/api/test_generation_api.py`

- [ ] **Step 1: Strengthen generate endpoint assertions**

Assert `POST /api/designs/{design_id}/generate` returns status `202`, an `id`, status `queued`, and that `GET /api/jobs/{id}` reaches `succeeded`.

- [ ] **Step 2: Add PATCH spec async test**

Generate an initial version, patch a scalar field through `/api/designs/{design_id}/spec`, assert the response is `202`, then poll the returned job and assert `succeeded` with a new `version_no`.

- [ ] **Step 3: Add failing backend API test**

Swap the router runner to a `JobRunner` using a backend that raises during generation. Assert the job status is `failed` and `/api/designs/{design_id}/versions` does not list the failed version.

- [ ] **Step 4: Run focused tests**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_generation_api.py -q`

Expected: all tests pass.

### Task 3: Async Runner Documentation

**Files:**
- Modify: `docs/async-job-runner-plan.md`

- [ ] **Step 1: Mark Phase 1 completed items**

Record `JobRecord`, `enqueue_generate`, `run_queued_job`, `storage/jobs`, `GET /api/jobs/{job_id}`, and BackgroundTasks generate/patch as completed.

- [ ] **Step 2: Mark remaining work**

Record route contract tests, frontend full-flow QA, failed diagnostic version isolation, and concurrent version locking as remaining or next.

### Task 4: Verification

**Files:**
- No source changes expected beyond tests and docs unless tests expose a defect.

- [ ] **Step 1: Run API tests**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api -q`

Expected: all API tests pass.

- [ ] **Step 2: Run frontend tests**

Run: `cd apps/web && npm test -- --run`

Expected: all frontend tests pass.

- [ ] **Step 3: Inspect git diff**

Run: `git status -sb && git diff --stat`

Expected: only planned test and documentation files changed.
