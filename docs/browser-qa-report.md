# Browser QA Report — 2026-05-18

**Commit:** f28e16f
**Backend:** CAD_BACKEND=fake, uvicorn on 127.0.0.1:8900
**Frontend:** Next.js dev server on localhost:3900

---

## 1. Happy Path: generate_design

| Step | Status | Notes |
|------|--------|-------|
| POST /api/designs/qa-demo/generate with YAML spec | PASS | Returns `job_id`, `status: "queued"`, `version_no: 1` |
| Poll GET /api/jobs/{id} | PASS | Transitions: queued → running → succeeded |
| Job response includes `duration_ms` | PASS | `duration_ms: 14.8` (float, not null) |
| Version list shows v1 | PASS | `[{"version_no": 1}]` |
| Version detail returns files | PASS | glb, step, vsp3, obj, etc. |
| Frontend loads CAD viewer | PASS | HTTP 200, page renders |
| Frontend fetches GLB file | PASS | /api/designs/qa-demo/versions/1/files/aircraft.glb accessible |

## 2. Modify Path: PATCH spec

| Step | Status | Notes |
|------|--------|-------|
| PATCH /api/designs/qa-demo/spec with `{"changes": [{"path": "wing.span.value", "value": 15}]}` | PASS | Returns new job, version_no: 2 |
| Poll until succeeded | PASS | `status: "succeeded"`, `duration_ms: 31.7` |
| Version list updates | PASS | `[{"version_no": 1}, {"version_no": 2}]` |
| Version 2 files accessible | PASS | All artifact files present |

### PATCH error handling

| Input | Result |
|-------|--------|
| Invalid path `aircraft.wing.span.value` | 400: "nonexistent path component" |
| Raw value instead of scalar `{"path": "wing.span", "value": 15}` | 400: Pydantic validation error |
| Empty changes array | 400: "changes array is required and must not be empty" |

## 3. Diagnostics API

| Step | Status | Notes |
|------|--------|-------|
| GET /api/jobs/{id}/diagnostics (succeeded) | PASS | Returns job, version_status, generation_log, validation_report, files_exist |
| All 5 fields present | PASS | job (dict), version_status (dict), generation_log (dict), validation_report (dict), files_exist (dict) |
| files_exist values | PASS | All expected files: True |
| GET /api/jobs/nonexistent/diagnostics | PASS | Returns 404 `{"detail": "job not found"}` |
| No 500 errors observed | PASS | All error responses are 400 or 404 |

## 4. Version List Filtering

| Condition | Result |
|-----------|--------|
| After 2 succeeded generations | `[v1, v2]` — correct |
| No failed versions appear | Confirmed (no failures generated in this session) |

## 5. duration_ms Unification

| Location | Field Name | Status |
|----------|-----------|--------|
| Job response (GET /api/jobs/{id}) | `duration_ms` | PASS — float value present |
| Job create response | `duration_ms` | PASS — null for pending, float for completed |
| Diagnostics job object | `duration_ms` | PASS — 14.8 / 31.7 |

## 6. Frontend Tests

| Suite | Count | Status |
|-------|-------|--------|
| cadPreviewSource | 4 | PASS |
| cadPreviewStatus | 2 | PASS |
| pickingOverlay | 2 | PASS |
| previewGeometry | 2 | PASS |
| threePreviewModel | 3 | PASS |
| chatSse | 1 | PASS |
| jobPolling | 2 | PASS |
| generationFlow | 12 | PASS |
| jobDiagnostics | 6 | PASS |
| **Total** | **34** | **PASS** |

## 7. Backend Tests

| Suite | Count | Status |
|-------|-------|--------|
| All pytest tests | 213 passed, 1 skipped | PASS |

## 8. Frontend Build

| Command | Status |
|---------|--------|
| `npm run build` | PASS — no errors, all routes generated |

## Issues Found

None.

## Manual Browser Verification Needed

The following require manual browser interaction (cannot be verified via API alone):

- [ ] Chat SSE stream: send natural language message, verify tool card spinner → done transition
- [ ] CAD viewer: verify 3D model loads and renders after generation
- [ ] ParameterPanel: verify values populate and can be modified
- [ ] Selected-part click in CAD viewer
- [ ] DiagnosticsPanel: click "查看诊断" on failed tool card
- [ ] "诊断信息暂不可用" display when diagnostics returns null
- [ ] Console errors during normal operation
- [ ] Network tab: polling stops after succeeded/failed
