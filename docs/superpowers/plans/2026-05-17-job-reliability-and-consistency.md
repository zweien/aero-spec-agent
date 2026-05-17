# Job Reliability and Version Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hardening the async job lifecycle — structured API schemas, centralized version status management, failed job diagnostics, concurrency tests, job-version consistency tests, unified frontend types, and QA checklist.

**Architecture:** Extract version_status.json I/O into a dedicated module. Add Pydantic response schemas for type-safe API output. Add diagnostics endpoint for failed jobs. Add concurrency and consistency tests. Create shared frontend Job types.

**Tech Stack:** Python 3.11+ (FastAPI, Pydantic), TypeScript/Next.js, threading + ThreadPoolExecutor for concurrency tests.

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `services/api/app/schemas/job.py` | Pydantic models for JobResponse, JobStatus |
| Create | `services/api/app/services/version_status.py` | Centralized version_status.json read/write |
| Modify | `services/api/app/services/version_store.py` | Delegate version_status to version_status module |
| Modify | `services/api/app/services/job_runner.py` | Use version_status module, write richer status data |
| Modify | `services/api/app/routers/designs.py` | Use JobResponse schema, add diagnostics endpoint |
| Modify | `services/api/app/services/chat_service.py` | Use JobResponse schema in _job_result |
| Create | `apps/web/src/types/job.ts` | Unified JobStatus, JobRecord types |
| Modify | `apps/web/src/components/chat/jobPolling.ts` | Import from types/job.ts |
| Modify | `apps/web/src/components/chat/ChatPanel.tsx` | Import from types/job.ts |
| Modify | `apps/web/src/app/page.tsx` | Import from types/job.ts |
| Create | `docs/frontend-qa-checklist.md` | QA checklist for all generation paths |
| Modify | `tests/api/test_job_runner.py` | Concurrency tests, consistency tests |

---

### Task 1: Create JobResponse Pydantic schema

**Files:**
- Create: `services/api/app/schemas/job.py`
- Modify: `services/api/app/routers/designs.py:21-24`

- [ ] **Step 1: Create `services/api/app/schemas/job.py`**

```python
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobResponse(BaseModel):
    id: str
    job_id: str = Field(description="Alias for id, kept for frontend compat")
    design_id: str
    version_no: int
    status: JobStatus
    progress: int = 0
    current_step: str = ""
    error_message: str | None = None
    files: dict[str, str] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    duration: float | None = None
    version_status: str = "pending"

    model_config = {"from_attributes": True}


def job_to_response(job: Any) -> dict[str, Any]:
    """Convert a JobRecord (dataclass) to a JobResponse-compatible dict."""
    data = {
        "id": job.id,
        "job_id": job.id,
        "design_id": job.design_id,
        "version_no": job.version_no,
        "status": job.status,
        "progress": job.progress,
        "current_step": job.current_step,
        "error_message": job.error_message,
        "files": job.files,
        "created_at": getattr(job, "created_at", ""),
        "updated_at": getattr(job, "updated_at", ""),
        "duration": getattr(job, "duration", None),
        "version_status": getattr(job, "version_status", "pending"),
    }
    return JobResponse.model_validate(data).model_dump()
```

- [ ] **Step 2: Update designs.py to use `job_to_response`**

In `services/api/app/routers/designs.py`, replace the `_job_response` function and update imports:

Add import at top:
```python
from services.api.app.schemas.job import job_to_response
```

Replace the `_job_response` function:
```python
def _job_response(job) -> dict[str, object]:
    return job_to_response(job)
```

- [ ] **Step 3: Run tests**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest -q`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add services/api/app/schemas/job.py services/api/app/routers/designs.py
git commit -m "feat(api): add JobResponse Pydantic schema for type-safe job output"
```

---

### Task 2: Centralize version_status.json read/write

**Files:**
- Create: `services/api/app/services/version_status.py`
- Modify: `services/api/app/services/version_store.py` — delegate to version_status module
- Modify: `services/api/app/services/job_runner.py` — write richer status data via version_status

- [ ] **Step 1: Create `services/api/app/services/version_status.py`**

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.api.app.services.version_store import VersionStore


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class VersionStatus:
    """Centralized read/write for version_status.json files."""

    def __init__(self, store: VersionStore) -> None:
        self._store = store

    def _path(self, design_id: str, version_no: int) -> Path:
        return self._store.version_dir(design_id, version_no) / "version_status.json"

    def write(
        self,
        design_id: str,
        version_no: int,
        *,
        status: str,
        job_id: str | None = None,
        current_step: str = "",
        error_message: str | None = None,
        files: dict[str, str] | None = None,
        duration_ms: float | None = None,
    ) -> None:
        existing = self.read_raw(design_id, version_no) or {}
        data: dict[str, Any] = {
            "status": status,
            "version_no": version_no,
            "design_id": design_id,
            "job_id": job_id,
            "updated_at": _utcnow_iso(),
        }
        if current_step:
            data["current_step"] = current_step
        if error_message:
            data["error_message"] = error_message
        if files:
            data["files"] = {k: str(v) for k, v in files.items()}
        if duration_ms is not None:
            data["duration_ms"] = duration_ms
        created_at = existing.get("created_at")
        if created_at:
            data["created_at"] = created_at
        self._path(design_id, version_no).write_text(
            json.dumps(data, ensure_ascii=False),
            encoding="utf-8",
        )

    def write_pending(self, design_id: str, version_no: int) -> None:
        now = _utcnow_iso()
        data: dict[str, Any] = {
            "status": "pending",
            "version_no": version_no,
            "design_id": design_id,
            "job_id": None,
            "created_at": now,
            "updated_at": now,
        }
        self._path(design_id, version_no).write_text(
            json.dumps(data, ensure_ascii=False),
            encoding="utf-8",
        )

    def read(self, design_id: str, version_no: int) -> str:
        raw = self.read_raw(design_id, version_no)
        if raw is None:
            return "succeeded"
        return raw.get("status", "succeeded")

    def read_raw(self, design_id: str, version_no: int) -> dict[str, Any] | None:
        path = self._path(design_id, version_no)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
```

- [ ] **Step 2: Update VersionStore to delegate to VersionStatus**

In `services/api/app/services/version_store.py`:

Add import:
```python
from services.api.app.services.version_status import VersionStatus
```

In `__init__`, add:
```python
self.version_status = VersionStatus(self)
```

Replace `create_version_dir` to use `self.version_status.write_pending`:
```python
def create_version_dir(self, design_id: str) -> tuple[int, Path]:
    design_id = self._validate_design_id(design_id)
    versions_root = self.root / "designs" / design_id / "versions"
    with self._lock:
        versions_root.mkdir(parents=True, exist_ok=True)
        existing = [
            int(p.name) for p in versions_root.iterdir() if p.is_dir() and p.name.isdigit()
        ]
        version_no = max(existing, default=0) + 1
        path = versions_root / str(version_no)
        path.mkdir(exist_ok=False)
    self.version_status.write_pending(design_id, version_no)
    return version_no, path
```

Note: `write_pending` is called outside `_lock` because it writes to its own file (version_status.json) inside an already-created directory. The lock only protects version number allocation + directory creation.

Remove `write_version_status` and `read_version_status` methods from VersionStore. Remove the `_utcnow_iso` helper. These are now handled by the `VersionStatus` class.

Update `list_versions` to use `self.version_status.read`:
```python
def list_versions(self, design_id: str) -> list[dict[str, object]]:
    design_id = self._validate_design_id(design_id)
    versions_root = self.root / "designs" / design_id / "versions"
    if not versions_root.exists():
        return []
    versions = []
    for path in sorted(versions_root.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else 0):
        if not (path.is_dir() and path.name.isdigit()):
            continue
        status_path = path / "version_status.json"
        if status_path.exists():
            data = json.loads(status_path.read_text(encoding="utf-8"))
            if data.get("status") != "succeeded":
                continue
        versions.append({"version_no": int(path.name)})
    return versions
```

(The `list_versions` logic stays inline since it does a batch scan, not a per-version method call.)

- [ ] **Step 3: Update JobRunner to use VersionStatus**

In `services/api/app/services/job_runner.py`, update `_run_generation` to use richer status writes:

Replace the two `self.store.write_version_status(...)` calls in the `try` and `except` blocks:

In the success path (after `job.files = ...`):
```python
self.store.version_status.write(
    job.design_id, job.version_no,
    status="succeeded",
    job_id=job.id,
    current_step="succeeded",
    files=job.files,
    duration_ms=job.duration * 1000 if job.duration else None,
)
```

In the failure path (after `job.error_message = ...`):
```python
self.store.version_status.write(
    job.design_id, job.version_no,
    status="failed",
    job_id=job.id,
    current_step="failed",
    error_message=job.error_message,
    duration_ms=job.duration * 1000 if job.duration else None,
)
```

Remove the `from services.api.app.services.version_store import VersionStore` import's reliance on write_version_status/read_version_status.

- [ ] **Step 4: Run full tests**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest -q`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add services/api/app/services/version_status.py services/api/app/services/version_store.py services/api/app/services/job_runner.py
git commit -m "refactor: centralize version_status.json read/write into VersionStatus module"
```

---

### Task 3: Add failed job diagnostics API

**Files:**
- Modify: `services/api/app/routers/designs.py` — add GET /api/jobs/{job_id}/diagnostics

- [ ] **Step 1: Write failing test**

Add to `tests/api/test_generation_api.py`:

```python
def test_diagnostics_endpoint_returns_job_and_version_details(client: TestClient):
    spec_text = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml").read_text(encoding="utf-8")
    first_job = client.post("/api/designs/demo-diag/generate", content=spec_text).json()
    _wait_for_job(client, first_job["id"])

    response = client.get(f"/api/jobs/{first_job['id']}/diagnostics")

    assert response.status_code == 200
    data = response.json()
    assert data["job"]["id"] == first_job["id"]
    assert data["job"]["status"] == "succeeded"
    assert data["version_status"] is not None
    assert data["version_status"]["status"] == "succeeded"


def test_diagnostics_endpoint_for_failed_job(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir):
            raise RuntimeError("cad exploded")

    spec_text = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml").read_text(encoding="utf-8")
    first_job = client.post("/api/designs/demo-diag-fail/generate", content=spec_text).json()
    _wait_for_job(client, first_job["id"])

    failing_runner = JobRunner(
        store=designs_router.runner.store,
        backend=FailingBackend(),
    )
    monkeypatch.setattr(designs_router, "runner", failing_runner)

    response = client.post("/api/designs/demo-diag-fail/generate", content=spec_text)
    job = response.json()
    _wait_for_job(client, job["id"])

    response = client.get(f"/api/jobs/{job['id']}/diagnostics")

    assert response.status_code == 200
    data = response.json()
    assert data["job"]["status"] == "failed"
    assert data["version_status"]["status"] == "failed"
    assert data["generation_log"] is None or isinstance(data["generation_log"], dict)


def test_diagnostics_endpoint_returns_404_for_missing_job(client: TestClient):
    response = client.get("/api/jobs/nonexistent-job-id/diagnostics")

    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_generation_api.py::test_diagnostics_endpoint_returns_job_and_version_details -q`
Expected: FAIL — 405 or 404

- [ ] **Step 3: Add diagnostics endpoint**

Add to `services/api/app/routers/designs.py`:

```python
import json as _json
from pathlib import Path as _Path


@router.get("/jobs/{job_id}/diagnostics")
def get_job_diagnostics(job_id: str):
    job = runner.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    version_status = runner.store.version_status.read_raw(job.design_id, job.version_no)

    generation_log = None
    log_path = runner.store.version_dir(job.design_id, job.version_no) / "generation_log.json"
    if log_path.exists():
        try:
            generation_log = _json.loads(log_path.read_text(encoding="utf-8"))
        except Exception:
            generation_log = None

    return {
        "job": _job_response(job),
        "version_status": version_status,
        "generation_log": generation_log,
    }
```

Note: If `json` is already imported (it is — line 2: `import json`), use `json` directly instead of `_json`. Check the imports in the file and use the appropriate name. Same for `Path` — check if it's already imported.

- [ ] **Step 4: Run tests**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_generation_api.py -q`
Expected: All PASS

- [ ] **Step 5: Run full suite**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest -q`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add services/api/app/routers/designs.py tests/api/test_generation_api.py
git commit -m "feat(api): add GET /api/jobs/{job_id}/diagnostics endpoint"
```

---

### Task 4: Add concurrency tests for version allocation

**Files:**
- Modify: `tests/api/test_job_runner.py`

- [ ] **Step 1: Write concurrency test**

Add to `tests/api/test_job_runner.py`:

```python
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


def test_concurrent_create_version_dir_produces_unique_numbers(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    num_versions = 20

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(store.create_version_dir, "demo") for _ in range(num_versions)]
        results = [f.result() for f in as_completed(futures)]

    version_nos = sorted(vno for vno, _ in results)
    assert version_nos == list(range(1, num_versions + 1))

    for vno, path in results:
        assert (path / "version_status.json").exists()
        data = json.loads((path / "version_status.json").read_text())
        assert data["status"] == "pending"


def test_concurrent_enqueue_generate_produces_unique_versions(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))
    num_jobs = 10

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(runner.enqueue_generate, "demo", spec) for _ in range(num_jobs)]
        jobs = [f.result() for f in as_completed(futures)]

    version_nos = sorted(job.version_no for job in jobs)
    assert version_nos == list(range(1, num_jobs + 1))
    assert len(set(job.id for job in jobs)) == num_jobs
```

- [ ] **Step 2: Run tests**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_job_runner.py::test_concurrent_create_version_dir_produces_unique_numbers tests/api/test_job_runner.py::test_concurrent_enqueue_generate_produces_unique_versions -q`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/api/test_job_runner.py
git commit -m "test: add concurrency tests for version allocation uniqueness"
```

---

### Task 5: Add job-version consistency tests

**Files:**
- Modify: `tests/api/test_job_runner.py`

- [ ] **Step 1: Write consistency tests**

Add to `tests/api/test_job_runner.py`:

```python
def test_succeeded_job_version_status_consistency(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))

    job = runner.generate(design_id="demo", spec=spec)

    assert job.status == "succeeded"
    assert store.version_status.read("demo", job.version_no) == "succeeded"
    assert job.version_status == "succeeded"
    assert store.list_versions("demo") == [{"version_no": 1}]


def test_failed_job_version_status_consistency(tmp_path: Path):
    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir):
            raise RuntimeError("boom")

    store = VersionStore(root=tmp_path / "storage")
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))
    JobRunner(store=store, backend=FakeCadBackend()).generate(design_id="demo", spec=spec)

    runner = JobRunner(store=store, backend=FailingBackend())
    job = runner.enqueue_generate(design_id="demo", spec=spec)
    runner.run_queued_job(job.id, spec)

    failed = runner.get(job.id)
    assert failed is not None
    assert failed.status == "failed"
    assert store.version_status.read("demo", 2) == "failed"
    assert failed.version_status == "failed"
    assert store.list_versions("demo") == [{"version_no": 1}]


def test_pending_version_not_in_list_versions(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    store.create_version_dir("demo")

    assert store.list_versions("demo") == []


def test_mixed_statuses_list_versions_only_succeeded(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))

    # v1: succeeded
    JobRunner(store=store, backend=FakeCadBackend()).generate(design_id="demo", spec=spec)
    # v2: pending (just create dir)
    store.create_version_dir("demo")
    # v3: failed
    class Fail(FakeCadBackend):
        def generate(self, spec, output_dir):
            raise RuntimeError("x")
    runner = JobRunner(store=store, backend=Fail())
    job = runner.enqueue_generate(design_id="demo", spec=spec)
    runner.run_queued_job(job.id, spec)
    # v4: succeeded
    JobRunner(store=store, backend=FakeCadBackend()).generate(design_id="demo", spec=spec)

    assert store.list_versions("demo") == [{"version_no": 1}, {"version_no": 4}]
```

- [ ] **Step 2: Run tests**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_job_runner.py::test_succeeded_job_version_status_consistency tests/api/test_job_runner.py::test_failed_job_version_status_consistency tests/api/test_job_runner.py::test_pending_version_not_in_list_versions tests/api/test_job_runner.py::test_mixed_statuses_list_versions_only_succeeded -q`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/api/test_job_runner.py
git commit -m "test: add job-version consistency tests for succeeded, failed, pending states"
```

---

### Task 6: Unify frontend Job types

**Files:**
- Create: `apps/web/src/types/job.ts`
- Modify: `apps/web/src/components/chat/jobPolling.ts`
- Modify: `apps/web/src/components/chat/ChatPanel.tsx`
- Modify: `apps/web/src/app/page.tsx`

- [ ] **Step 1: Create `apps/web/src/types/job.ts`**

```typescript
export type JobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed";

export type JobRecord = {
  id: string;
  job_id: string;
  design_id: string;
  version_no: number;
  status: JobStatus;
  progress: number;
  current_step: string;
  error_message: string | null;
  files: Record<string, string>;
  created_at: string;
  updated_at: string;
  duration: number | null;
  version_status: string;
};

export type JobPollResult = {
  id: string;
  design_id?: string;
  version_no?: number;
  status: JobStatus;
  progress?: number;
  files?: string[];
};

export function isTerminalStatus(status: string | undefined): status is "succeeded" | "failed" {
  return status === "succeeded" || status === "failed";
}

export function isSucceeded(status: string | undefined): boolean {
  return status === "succeeded";
}
```

- [ ] **Step 2: Update jobPolling.ts**

Replace the entire content of `apps/web/src/components/chat/jobPolling.ts`:

```typescript
import type { JobStatus, JobPollResult } from "@/types/job";
import { isTerminalStatus } from "@/types/job";

export type { JobStatus, JobPollResult };

type GenerationJob = {
  id: string;
  design_id?: string;
  version_no?: number;
  status?: JobStatus;
  progress?: number;
  current_step?: string;
  error_message?: string | null;
  files?: Record<string, string> | string[];
};

type WaitForGenerationJobOptions = {
  apiBaseUrl: string;
  jobId: string;
  intervalMs?: number;
  maxAttempts?: number;
  fetchFn?: typeof fetch;
};

export async function waitForGenerationJob({
  apiBaseUrl,
  jobId,
  intervalMs = 1000,
  maxAttempts = 120,
  fetchFn = fetch,
}: WaitForGenerationJobOptions): Promise<JobPollResult> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const response = await fetchFn(`${apiBaseUrl}/api/jobs/${jobId}`);
    if (!response.ok) {
      throw new Error(`Job API failed with status ${response.status}`);
    }

    const job = (await response.json()) as GenerationJob;
    if (job.status === "failed") {
      throw new Error(job.error_message ?? "生成任务失败");
    }
    if (job.status === "succeeded") {
      return normalizeJobResult(job);
    }

    if (attempt < maxAttempts - 1) {
      await delay(intervalMs);
    }
  }

  throw new Error("生成任务超时");
}

function normalizeJobResult(job: GenerationJob): JobPollResult {
  return {
    id: job.id,
    design_id: job.design_id,
    version_no: job.version_no,
    status: job.status ?? "succeeded",
    progress: job.progress,
    files: normalizeFiles(job.files),
  };
}

function normalizeFiles(files: GenerationJob["files"]): string[] | undefined {
  if (Array.isArray(files)) return files;
  if (files && typeof files === "object") return Object.keys(files);
  return undefined;
}

function delay(ms: number): Promise<void> {
  if (ms <= 0) return Promise.resolve();
  return new Promise((resolve) => globalThis.setTimeout(resolve, ms));
}
```

- [ ] **Step 3: Update ChatPanel.tsx imports**

In `apps/web/src/components/chat/ChatPanel.tsx`, change the import:

```typescript
import { waitForGenerationJob } from "./jobPolling";
```

No other changes needed — `ChatPanel.tsx` only uses `waitForGenerationJob` and `GenerationCompleteData` (which is a local type, not from jobPolling).

- [ ] **Step 4: Update page.tsx imports**

In `apps/web/src/app/page.tsx`, change the import:

```typescript
import { waitForGenerationJob } from "@/components/chat/jobPolling";
```

No other changes needed — `page.tsx` only uses `waitForGenerationJob`.

- [ ] **Step 5: Verify frontend builds**

Run: `cd /home/z/codebase/aero-spec-agent/apps/web && npm run build`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/types/job.ts apps/web/src/components/chat/jobPolling.ts apps/web/src/components/chat/ChatPanel.tsx apps/web/src/app/page.tsx
git commit -m "feat(frontend): unify Job types into types/job.ts, centralize status helpers"
```

---

### Task 7: Create frontend QA checklist

**Files:**
- Create: `docs/frontend-qa-checklist.md`

- [ ] **Step 1: Create the checklist**

Write to `docs/frontend-qa-checklist.md`:

```markdown
# Frontend QA Checklist — Generation & Version Paths

## 1. Chat: generate_design

- [ ] Send "设计一架翼展12米的无人机" via chat
- [ ] SSE event `generation_started` received with `job_id`
- [ ] `waitForGenerationJob` polls until `succeeded`
- [ ] Tool card shows "done" state
- [ ] `loadVersion` updates CAD viewer, parameters, version list
- [ ] New version appears in VersionPanel

## 2. Chat: modify_design

- [ ] With existing design, send "把翼展改成15米"
- [ ] SSE event `generation_started` received with `job_id`
- [ ] `waitForGenerationJob` polls until `succeeded`
- [ ] Parameters panel reflects updated value
- [ ] CAD viewer loads new version

## 3. Chat: modify_selected_part

- [ ] Select a part (e.g. part:fuselage) in CAD viewer
- [ ] Send "加长2米"
- [ ] SSE event `generation_started` received with `job_id`
- [ ] `waitForGenerationJob` polls until `succeeded`
- [ ] Selected part reflects change in parameters and viewer

## 4. ParameterPanel PATCH

- [ ] Modify a parameter in ParameterPanel
- [ ] Click apply
- [ ] PATCH request sent to `/api/designs/{id}/spec`
- [ ] Response contains `job_id` with `status: "queued"`
- [ ] `waitForGenerationJob` polls until `succeeded`
- [ ] `loadVersion` + `fetchVersionList` update UI
- [ ] Tool card shows completed state

## 5. Failed job handling

- [ ] Trigger a generation that will fail (e.g. set CAD_BACKEND to failing mode)
- [ ] `waitForGenerationJob` receives `status: "failed"`
- [ ] Error message displayed to user via tool card fail state
- [ ] Failed version does NOT appear in version list
- [ ] GET /api/jobs/{id}/diagnostics returns error details

## 6. Version list filtering

- [ ] After a mix of succeeded and failed jobs, version list shows only succeeded
- [ ] Legacy versions (no version_status.json) still appear
- [ ] Pending versions (in-progress) do NOT appear
- [ ] Version numbers are sequential and skip failed/pending
```

- [ ] **Step 2: Commit**

```bash
git add docs/frontend-qa-checklist.md
git commit -m "docs: add frontend QA checklist for generation and version paths"
```

---

### Task 8: Final verification

- [ ] **Step 1: Run full backend test suite**

Run: `cd /home/z/codebase/aero-spec-agent && CAD_BACKEND=fake .venv/bin/python -m pytest tests/api -q`
Expected: All PASS

- [ ] **Step 2: Run frontend build**

Run: `cd /home/z/codebase/aero-spec-agent/apps/web && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Run frontend tests (if configured)**

Run: `cd /home/z/codebase/aero-spec-agent/apps/web && npm test -- --run 2>&1 || echo "No test runner configured or tests pass"`
Expected: Pass or no test runner

- [ ] **Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "chore: final fixes for job reliability and consistency"
```
