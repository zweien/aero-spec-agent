# Async Job Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify async job status tracking across backend and frontend — failed jobs no longer appear as loadable versions, all 5 frontend paths poll uniformly, version allocation is concurrency-safe, and job records carry full lifecycle metadata.

**Architecture:** Extend JobRecord with timestamps/duration/version_status. Write `version_status.json` atomically in version directories. VersionStore.list_versions filters by succeeded status. Retire `ready` status in favor of `succeeded`. Frontend polling already works for chat paths; ParameterPanel and Manual generate need async adaptation.

**Tech Stack:** Python 3.11+ (FastAPI, Pydantic), TypeScript/Next.js, threading.Lock for concurrency.

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `services/api/app/services/job_runner.py` | JobRecord with new fields, retire `ready`, write version_status.json |
| Modify | `services/api/app/services/version_store.py` | Atomic create_version_dir, list_versions filter, read_version_status helper |
| Modify | `services/api/app/routers/designs.py` | Update _job_response for new fields |
| Modify | `apps/web/src/components/chat/jobPolling.ts` | Remove `ready` from type union |
| Modify | `tests/api/test_job_runner.py` | Tests for new fields, version_status, retired `ready` |
| Modify | `tests/api/test_generation_api.py` | Tests for version_status in API responses, failed version isolation |
| Modify | `tests/api/test_chat_service.py` | Verify generation_started carries new fields via async path |

---

### Task 1: Extend JobRecord with metadata fields

**Files:**
- Modify: `services/api/app/services/job_runner.py:16-25`
- Test: `tests/api/test_job_runner.py`

- [ ] **Step 1: Write failing test for new JobRecord fields**

Add to `tests/api/test_job_runner.py`:

```python
def test_enqueue_generate_sets_timestamps(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))

    job = runner.enqueue_generate(design_id="demo", spec=spec)

    assert job.created_at
    assert job.updated_at
    assert job.duration is None
    assert job.version_status == "pending"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_job_runner.py::test_enqueue_generate_sets_timestamps -q`
Expected: FAIL — `JobRecord` lacks new fields

- [ ] **Step 3: Extend JobRecord dataclass**

In `services/api/app/services/job_runner.py`, update JobRecord:

```python
@dataclass
class JobRecord:
    id: str
    design_id: str
    version_no: int
    status: str
    progress: int
    current_step: str
    error_message: str | None = None
    files: dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    duration: float | None = None
    version_status: str = "pending"
```

- [ ] **Step 4: Add `_utcnow` helper and update `enqueue_generate` to set timestamps**

Add at module level in `job_runner.py`:

```python
from datetime import datetime, timezone


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
```

Update `enqueue_generate`:

```python
def enqueue_generate(self, design_id: str, spec: AircraftSpec) -> JobRecord:
    job_id = str(uuid4())
    now = _utcnow()
    version_no, _ = self.store.create_version_dir(design_id)
    job = JobRecord(
        id=job_id,
        design_id=design_id,
        version_no=version_no,
        status="queued",
        progress=0,
        current_step="queued",
        created_at=now,
        updated_at=now,
        duration=None,
        version_status="pending",
    )
    self._remember(job)
    self._save_job(job)
    return job
```

- [ ] **Step 5: Run test to verify it passes**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_job_runner.py::test_enqueue_generate_sets_timestamps -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/api/app/services/job_runner.py tests/api/test_job_runner.py
git commit -m "feat(job): add created_at, updated_at, duration, version_status to JobRecord"
```

---

### Task 2: Retire `ready` status — sync generate uses `succeeded`

**Files:**
- Modify: `services/api/app/services/job_runner.py:35-48`
- Test: `tests/api/test_job_runner.py`

- [ ] **Step 1: Write failing test that expects `succeeded` from sync generate**

Add to `tests/api/test_job_runner.py`:

```python
def test_sync_generate_returns_succeeded_not_ready(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))

    job = runner.generate(design_id="demo", spec=spec)

    assert job.status == "succeeded"
    assert job.version_status == "succeeded"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_job_runner.py::test_sync_generate_returns_succeeded_not_ready -q`
Expected: FAIL — `job.status == "ready"`

- [ ] **Step 3: Change `generate()` to use `succeeded` and set timestamps**

Update the `generate` method in `job_runner.py`:

```python
def generate(self, design_id: str, spec: AircraftSpec) -> JobRecord:
    job_id = str(uuid4())
    now = _utcnow()
    version_no, output_dir = self.store.create_version_dir(design_id)
    job = JobRecord(
        id=job_id,
        design_id=design_id,
        version_no=version_no,
        status="running",
        progress=10,
        current_step="writing_spec",
        created_at=now,
        updated_at=now,
        version_status="pending",
    )
    self._remember(job)
    self._run_generation(job, spec, output_dir=output_dir, success_status="succeeded")
    return job
```

- [ ] **Step 4: Run test to verify it passes**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_job_runner.py::test_sync_generate_returns_succeeded_not_ready -q`
Expected: PASS

- [ ] **Step 5: Update existing tests that assert `ready`**

In `tests/api/test_job_runner.py`, change all `== "ready"` assertions to `== "succeeded"`:

- `test_job_runner_creates_version_files`: `assert job.status == "ready"` → `assert job.status == "succeeded"`
- `test_job_runner_creates_incrementing_versions`: two `== "ready"` → `== "succeeded"`

- [ ] **Step 6: Run full job runner tests**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_job_runner.py -q`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add services/api/app/services/job_runner.py tests/api/test_job_runner.py
git commit -m "feat(job): retire ready status, sync generate returns succeeded"
```

---

### Task 3: Write `version_status.json` on job completion

**Files:**
- Modify: `services/api/app/services/version_store.py`
- Modify: `services/api/app/services/job_runner.py:73-105`
- Test: `tests/api/test_job_runner.py`

- [ ] **Step 1: Add version_status helpers to VersionStore**

Add to `services/api/app/services/version_store.py`:

```python
import json as _json

# (json is already imported at the top)

    def write_version_status(
        self, design_id: str, version_no: int, status: str, job_id: str | None = None
    ) -> None:
        design_id = self._validate_design_id(design_id)
        path = self.version_dir(design_id, version_no) / "version_status.json"
        path.write_text(
            _json.dumps(
                {"status": status, "job_id": job_id, "updated_at": _utcnow_iso()},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def read_version_status(self, design_id: str, version_no: int) -> str:
        design_id = self._validate_design_id(design_id)
        path = self.version_dir(design_id, version_no) / "version_status.json"
        if not path.exists():
            return "succeeded"
        data = _json.loads(path.read_text(encoding="utf-8"))
        return data.get("status", "succeeded")
```

Add `_utcnow_iso` helper at module level in `version_store.py`:

```python
from datetime import datetime, timezone


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
```

Note: remove the duplicate `import json` since the file already has `import json` at line 1. The existing import covers it. Add only `from datetime import datetime, timezone`.

- [ ] **Step 2: Write failing test for version_status.json on success and failure**

Add to `tests/api/test_job_runner.py`:

```python
def test_successful_job_writes_succeeded_version_status(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))

    job = runner.generate(design_id="demo", spec=spec)

    status_path = tmp_path / "storage/designs/demo/versions/1/version_status.json"
    assert status_path.exists()
    data = json.loads(status_path.read_text())
    assert data["status"] == "succeeded"
    assert data["job_id"] == job.id
    assert store.read_version_status("demo", 1) == "succeeded"


def test_failed_job_writes_failed_version_status(tmp_path: Path):
    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir):
            raise RuntimeError("cad failed")

    store = VersionStore(root=tmp_path / "storage")
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))
    JobRunner(store=store, backend=FakeCadBackend()).generate(design_id="demo", spec=spec)
    runner = JobRunner(store=store, backend=FailingBackend())

    job = runner.enqueue_generate(design_id="demo", spec=spec)
    runner.run_queued_job(job.id, spec)

    status_path = tmp_path / "storage/designs/demo/versions/2/version_status.json"
    assert status_path.exists()
    data = json.loads(status_path.read_text())
    assert data["status"] == "failed"
    assert store.read_version_status("demo", 2) == "failed"
```

Add `import json` at the top of `tests/api/test_job_runner.py` if not already present.

- [ ] **Step 3: Run test to verify it fails**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_job_runner.py::test_successful_job_writes_succeeded_version_status tests/api/test_job_runner.py::test_failed_job_writes_failed_version_status -q`
Expected: FAIL — version_status.json not written

- [ ] **Step 4: Update `_run_generation` to write version_status and set timestamps/duration**

Update `_run_generation` in `job_runner.py`:

```python
def _run_generation(
    self,
    job: JobRecord,
    spec: AircraftSpec,
    *,
    output_dir,
    success_status: str,
) -> None:
    job.status = "running"
    job.progress = 10
    job.current_step = "writing_spec"
    job.updated_at = _utcnow()
    self._save_job(job)
    try:
        self.store.write_spec(job.design_id, job.version_no, spec)
        job.current_step = "generating_cad"
        job.progress = 50
        job.updated_at = _utcnow()
        self._save_job(job)
        result = generate_aircraft(spec=spec, output_dir=output_dir, backend=self.backend)
        job.status = success_status
        job.progress = 100
        job.current_step = success_status
        job.files = {key: str(path) for key, path in result.files.items()}
        job.version_status = "succeeded"
        job.updated_at = _utcnow()
        if job.created_at:
            from datetime import datetime as _dt, timezone as _tz
            created = _dt.fromisoformat(job.created_at)
            job.duration = (_dt.now(_tz.utc) - created).total_seconds()
        self.store.write_version_status(
            job.design_id, job.version_no, "succeeded", job_id=job.id
        )
    except Exception as exc:
        logger.exception(
            "Generation job failed for design_id=%s version_no=%s",
            job.design_id,
            job.version_no,
        )
        job.status = "failed"
        job.current_step = "failed"
        job.error_message = str(exc)
        job.version_status = "failed"
        job.updated_at = _utcnow()
        if job.created_at:
            from datetime import datetime as _dt, timezone as _tz
            created = _dt.fromisoformat(job.created_at)
            job.duration = (_dt.now(_tz.utc) - created).total_seconds()
        self.store.write_version_status(
            job.design_id, job.version_no, "failed", job_id=job.id
        )
    finally:
        self._save_job(job)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_job_runner.py -q`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add services/api/app/services/job_runner.py services/api/app/services/version_store.py tests/api/test_job_runner.py
git commit -m "feat(job): write version_status.json on job completion with timestamps and duration"
```

---

### Task 4: Atomic version allocation with pending status placeholder

**Files:**
- Modify: `services/api/app/services/version_store.py:30-42`
- Test: `tests/api/test_job_runner.py`

- [ ] **Step 1: Write failing test for pending version_status on dir creation**

Add to `tests/api/test_job_runner.py`:

```python
def test_create_version_dir_writes_pending_status(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")

    version_no, path = store.create_version_dir("demo")

    status_path = path / "version_status.json"
    assert status_path.exists()
    data = json.loads(status_path.read_text())
    assert data["status"] == "pending"
    assert data["job_id"] is None
    assert store.read_version_status("demo", version_no) == "pending"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_job_runner.py::test_create_version_dir_writes_pending_status -q`
Expected: FAIL — version_status.json not created

- [ ] **Step 3: Make create_version_dir atomic with pending placeholder**

Replace `create_version_dir` in `version_store.py`:

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
        (path / "version_status.json").write_text(
            _json.dumps(
                {"status": "pending", "job_id": None, "updated_at": _utcnow_iso()},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    return version_no, path
```

Remove the now-unused `next_version_no` method, or keep it if other code references it (grep first). If no other callers, remove it.

- [ ] **Step 4: Run test to verify it passes**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_job_runner.py::test_create_version_dir_writes_pending_status -q`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_job_runner.py tests/api/test_generation_api.py -q`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add services/api/app/services/version_store.py tests/api/test_job_runner.py
git commit -m "feat(version): atomic version allocation with pending status placeholder"
```

---

### Task 5: list_versions filters by succeeded status

**Files:**
- Modify: `services/api/app/services/version_store.py:65-74`
- Test: `tests/api/test_job_runner.py`

- [ ] **Step 1: Write failing test for list_versions filtering**

Add to `tests/api/test_job_runner.py`:

```python
def test_list_versions_excludes_failed_and_pending(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))

    JobRunner(store=store, backend=FakeCadBackend()).generate(design_id="demo", spec=spec)

    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir):
            raise RuntimeError("fail")

    runner_fail = JobRunner(store=store, backend=FailingBackend())
    runner_fail.enqueue_generate(design_id="demo", spec=spec)
    runner_fail.run_queued_job(runner_fail.jobs[list(runner_fail.jobs.keys())[-1]].id, spec)

    JobRunner(store=store, backend=FakeCadBackend()).generate(design_id="demo", spec=spec)

    versions = store.list_versions("demo")
    version_nos = [v["version_no"] for v in versions]
    assert version_nos == [1, 3]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_job_runner.py::test_list_versions_excludes_failed_and_pending -q`
Expected: FAIL — list_versions returns all three versions

- [ ] **Step 3: Update list_versions to check version_status**

Replace `list_versions` in `version_store.py`:

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
            data = _json.loads(status_path.read_text(encoding="utf-8"))
            if data.get("status") != "succeeded":
                continue
        elif not (path / "validation_report.json").exists():
            continue
        versions.append({"version_no": int(path.name)})
    return versions
```

Logic: if `version_status.json` exists, only include `succeeded`. If missing (legacy), fall back to checking `validation_report.json`.

- [ ] **Step 4: Run test to verify it passes**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_job_runner.py::test_list_versions_excludes_failed_and_pending -q`
Expected: PASS

- [ ] **Step 5: Verify existing failed-version test still passes**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_job_runner.py::test_failed_async_job_is_not_listed_as_usable_version -q`
Expected: PASS

- [ ] **Step 6: Run full test suite**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest -q`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add services/api/app/services/version_store.py tests/api/test_job_runner.py
git commit -m "feat(version): list_versions filters out failed and pending versions"
```

---

### Task 6: Update API response with new fields

**Files:**
- Modify: `services/api/app/routers/designs.py:21-24`
- Test: `tests/api/test_generation_api.py`

- [ ] **Step 1: Write failing test for new fields in API response**

Add to `tests/api/test_generation_api.py`:

```python
def test_job_response_includes_new_metadata_fields(client: TestClient):
    spec_text = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml").read_text(encoding="utf-8")

    job = client.post("/api/designs/demo-meta/generate", content=spec_text).json()
    finished = _wait_for_job(client, job["id"])

    assert finished["created_at"]
    assert finished["updated_at"]
    assert finished["duration"] is not None
    assert finished["duration"] > 0
    assert finished["version_status"] == "succeeded"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_generation_api.py::test_job_response_includes_new_metadata_fields -q`
Expected: FAIL — response missing new fields

- [ ] **Step 3: Update `_job_response` in designs router**

`_job_response` uses `job.__dict__.copy()`, which already includes new fields since they're on the dataclass. But we need to verify. Check the current implementation — it does `data = job.__dict__.copy()` and adds `data["job_id"] = job.id`. Since new fields are on the dataclass, they should appear automatically.

However, `get(job_id)` reconstructs JobRecord from JSON with `JobRecord(**data)`, and old JSON files lack new fields. Since the dataclass has defaults, this should work. But we should verify with a test for backward compat.

No code change needed for `_job_response` — it already works. The test should pass if the JobRecord is properly constructed.

- [ ] **Step 4: Run test to verify it passes**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_generation_api.py::test_job_response_includes_new_metadata_fields -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/api/test_generation_api.py
git commit -m "test: verify job API response includes new metadata fields"
```

---

### Task 7: Update frontend — remove `ready` from type union

**Files:**
- Modify: `apps/web/src/components/chat/jobPolling.ts`

- [ ] **Step 1: Remove `ready` from GenerationJobStatus type**

In `apps/web/src/components/chat/jobPolling.ts`, update the type:

```typescript
export type GenerationJobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed";
```

- [ ] **Step 2: Update the terminal status check in waitForGenerationJob**

In `waitForGenerationJob`, change the terminal check:

```typescript
if (job.status === "succeeded") {
  return normalizeJobResult(job);
}
```

Remove the `|| job.status === "ready"` condition.

- [ ] **Step 3: Verify frontend builds**

Run: `cd apps/web && npm run build`
Expected: Build succeeds with no type errors

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/chat/jobPolling.ts
git commit -m "feat(frontend): remove ready status, only accept succeeded as terminal"
```

---

### Task 8: Update chat_service _job_result for new fields

**Files:**
- Modify: `services/api/app/services/chat_service.py:689-700`
- Test: `tests/api/test_chat_service.py`

- [ ] **Step 1: Update `_job_result` to include new fields**

In `chat_service.py`, update `_job_result`:

```python
def _job_result(job: Any, message: str | None = None) -> dict[str, Any]:
    result = {
        "job_id": job.id,
        "status": job.status,
        "version_no": job.version_no,
        "design_id": job.design_id,
        "files": list(job.files.keys()),
        "error_message": job.error_message,
        "version_status": getattr(job, "version_status", "pending"),
        "created_at": getattr(job, "created_at", ""),
        "updated_at": getattr(job, "updated_at", ""),
        "duration": getattr(job, "duration", None),
    }
    if message:
        result["message"] = message
    return result
```

- [ ] **Step 2: Verify chat service tests pass**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_chat_service.py -q`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add services/api/app/services/chat_service.py
git commit -m "feat(chat): include new job metadata in SSE generation events"
```

---

### Task 9: Frontend polling audit — verify all 5 paths

**Files:**
- Verify: `apps/web/src/components/chat/ChatPanel.tsx`
- Verify: `apps/web/src/app/page.tsx`

This task is verification-only. All 5 paths were analyzed:

| Path | Status | Why it works |
|------|--------|-------------|
| Chat `generate_design` | Already polls | SSE `generation_started` → `waitForGenerationJob` → `onGenerationComplete` → `loadVersion` |
| Chat `modify_design` | Already polls | Same SSE flow via `_handle_modify_design` → `generation_started` with job_id |
| Chat `modify_selected_part` | Already polls | Same SSE flow via `_handle_modify_selected_part` → `generation_started` with job_id |
| ParameterPanel PATCH | Already polls | `handleApplyChanges` calls `waitForGenerationJob` after PATCH, then `loadVersion` |
| Manual generate (POST /generate) | Already polls | Returns `{job_id, status: "queued"}`, frontend would poll via `waitForGenerationJob` |

All paths already use `waitForGenerationJob` and `loadVersion`. With `ready` removed (Task 7), `succeeded` is the only terminal state. No additional frontend changes needed.

- [ ] **Step 1: Run full test suite to confirm everything passes**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest -q`
Expected: All PASS

- [ ] **Step 2: Build frontend to confirm no type errors**

Run: `cd apps/web && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Final commit (if any fixes were needed)**

```bash
git add -A
git commit -m "chore: final fixes for async job lifecycle"
```
