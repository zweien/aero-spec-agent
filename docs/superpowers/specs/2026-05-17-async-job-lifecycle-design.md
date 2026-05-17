# Async Job Lifecycle: Status, Concurrency, and Frontend Polling

## Problem

Four gaps in the current async job system:

- **P0**: Failed jobs create version directories that appear loadable in the UI.
- **P1**: Not all frontend paths (5 total) uniformly poll for job completion.
- **P2**: `create_version_dir` has a theoretical race in concurrent version allocation.
- **P3**: Job metadata lacks timestamps, duration, and version status linkage.

These are four facets of one problem — the async job lifecycle lacks end-to-end status tracking.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Version status storage | `version_status.json` per version dir | Simple, co-located with artifacts, no new index |
| Job status lifecycle | `queued → running → succeeded/failed` | Retire `ready`, unify sync/async |
| Concurrency protection | In-process lock around scan+mkdir+placeholder | Current `_lock` already works, just extend scope |
| Metadata scope | All fields at once | Single migration, no partial states |
| Frontend polling | Unify all 5 paths to `waitForGenerationJob` | Consistent UX, single error handling path |

## 1. Unified Status Model

### JobRecord extension

```python
@dataclass
class JobRecord:
    id: str
    design_id: str
    version_no: int
    status: str             # queued / running / succeeded / failed
    progress: int           # 0-100
    current_step: str
    error_message: str | None
    files: dict[str, str]
    created_at: str         # ISO 8601, set on enqueue
    updated_at: str         # ISO 8601, set on every status change
    duration: float | None  # seconds, computed on completion
    version_status: str     # pending / succeeded / failed
```

Status flow:

```
queued → running → succeeded (write version_status.json)
                 → failed    (write version_status.json, keep diagnostics)
```

- Retire `ready` status. Sync generation uses `succeeded`.
- Backward compat: missing fields default to `created_at=""`, `duration=None`, `version_status="succeeded"`.

### version_status.json

Written to each version directory:

```json
{"status": "succeeded", "job_id": "uuid", "updated_at": "2026-05-17T10:00:12Z"}
```

- `pending`: created atomically with version dir (concurrency placeholder).
- `succeeded`: written when job completes successfully.
- `failed`: written when job fails; version dir kept for diagnostics but excluded from `list_versions`.

### VersionStore.list_versions

- Scan version dirs, only return those where `version_status.json` exists and `status == "succeeded"`.
- Dirs without `version_status.json` (legacy) treated as `succeeded`.

## 2. Concurrency Protection

`create_version_dir` becomes atomic under `_lock`:

```python
def create_version_dir(self, design_id: str) -> tuple[int, Path]:
    with self._lock:
        versions_dir = self._base / design_id / "versions"
        existing = {int(d.name) for d in versions_dir.iterdir() if d.name.isdigit()}
        version_no = max(existing, default=0) + 1
        version_path = versions_dir / str(version_no)
        version_path.mkdir(parents=True, exist_ok=False)
        (version_path / "version_status.json").write_text(
            json.dumps({"status": "pending", "job_id": None, "updated_at": utcnow()})
        )
    return version_no, version_path
```

Three steps in one lock acquisition: scan max version → mkdir → write placeholder. No gap for concurrent requests to claim the same number.

## 3. Frontend Polling Unification

### Current state

| Path | Status |
|------|--------|
| Chat `generate_design` | Already polls via `waitForGenerationJob` |
| Chat `modify_design` | Already async, verify `job_id` in SSE |
| Chat `modify_selected_part` | Verify async path and SSE event |
| ParameterPanel PATCH | Sync call to `PATCH /api/designs/{id}/spec` |
| Manual generate | Sync call to `POST /api/designs/{id}/generate` |

### Backend changes

- `POST /api/designs/{id}/generate`: use `enqueue_generate`, return `{job_id, version_no, status: "queued"}`.
- `PATCH /api/designs/{id}/spec`: use `enqueue_generate`, return `{job_id, version_no, status: "queued"}`.
- `GET /api/jobs/{job_id}`: no change, already supports polling.

### Frontend changes

- ParameterPanel and Manual generate: extract `job_id` from response, call `waitForGenerationJob`, then `loadVersion`.
- `modify_design` / `modify_selected_part`: verify `generation_started` SSE carries `job_id`.
- Error display: `waitForGenerationJob` already throws on `failed`; catch and show `error_message`.

## 4. API Response and Storage

### GET /api/jobs/{job_id}

```json
{
  "id": "uuid",
  "design_id": "test-design",
  "version_no": 3,
  "status": "succeeded",
  "progress": 100,
  "current_step": "complete",
  "error_message": null,
  "files": {"aircraft.glb": "storage/..."},
  "created_at": "2026-05-17T10:00:00Z",
  "updated_at": "2026-05-17T10:00:12Z",
  "duration": 12.3,
  "version_status": "succeeded"
}
```

### Storage

- `storage/jobs/{job_id}.json`: full JobRecord serialization.
- `duration` computed on completion: `(now - created_at).total_seconds()`.

### Backward compatibility

- Old job files missing new fields: defaults in JobRecord constructor.
- Old version dirs without `version_status.json`: treated as `succeeded`.
- Existing frontend fields (`status`, `progress`, `error_message`, `files`) unchanged; new fields optional for frontend consumption.

## Testing

- `test_job_runner.py`: new field writes, duration calculation, version_status transitions.
- `test_version_store.py`: `list_versions` filters failed/pending, legacy compat.
- `test_generation_api.py`: async endpoints return `job_id`, poll to terminal state.
- `test_chat_service.py`: verify all three chat tool paths emit `generation_started` with `job_id`.
- Frontend: one integration test per polling path (manual QA for browser-level).
