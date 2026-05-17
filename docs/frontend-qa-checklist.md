# Frontend QA Checklist — Generation & Version Paths

## 1. Chat: generate_design

- [ ] Send "设计一架翼展12米的无人机" via chat
- [ ] SSE event `generation_started` received with `job_id`
- [ ] `waitForGenerationJob` polls until `succeeded`
- [ ] Tool card shows "done" state with ✓ icon
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
- [ ] Tool card shows ✗ icon with red border (tool-card-failed)
- [ ] Error message displayed to user via tool card fail state
- [ ] Failed version does NOT appear in version list
- [ ] GET /api/jobs/{id}/diagnostics returns error details

## 6. Failed job diagnostics

- [ ] Failed tool card shows "▸ 查看诊断" button
- [ ] Click "查看诊断" → fetches /api/jobs/{job_id}/diagnostics
- [ ] Diagnostics JSON displayed in expandable section
- [ ] Response includes: job, version_status, generation_log, validation_report, files_exist
- [ ] If generation_log or validation_report missing → shown as null
- [ ] Click "▾ 收起诊断" collapses the section

## 7. Version list filtering

- [ ] After a mix of succeeded and failed jobs, version list shows only succeeded
- [ ] Legacy versions (no version_status.json) still appear
- [ ] Pending versions (in-progress) do NOT appear
- [ ] Version numbers are sequential and skip failed/pending

## 8. Concurrent generation

- [ ] Rapidly click "generate" or "apply" multiple times
- [ ] Each request gets a unique version_no
- [ ] All version directories have version_status.json
- [ ] No 500 errors or duplicate version numbers
- [ ] Version list correctly shows only succeeded versions after all complete

## Manual Browser QA

### Setup
1. Start backend: `CAD_BACKEND=fake .venv/bin/python -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 3901`
2. Start frontend: `cd apps/web && npm run dev`
3. Open http://localhost:3900

### Test Sequence
1. **Happy path**: Design → Generate → Modify → Version switch
2. **Error path**: Open Settings → set cad_backend to failing → Generate → Verify diagnostics
3. **Reset**: Settings → set cad_backend back to fake → Verify normal operation
4. **Concurrency**: Rapid-fire "generate" 3-4 times → Check version numbers are sequential
5. **Browser DevTools**: Network tab → verify polling requests to /api/jobs/{id} stop after succeeded/failed
