# Frontend QA Checklist — Generation & Version Paths

## 1. Chat: generate_design

- [ ] Send "设计一架翼展12米的无人机" via chat
- [ ] SSE event `generation_started` received with `job_id`
- [ ] `resolveGenerationJob` polls until `succeeded`
- [ ] Tool card shows "done" state with ✓ icon
- [ ] `loadVersion` updates CAD viewer, parameters, version list
- [ ] New version appears in VersionPanel

## 2. Chat: modify_design

- [ ] With existing design, send "把翼展改成15米"
- [ ] SSE event `generation_started` received with `job_id`
- [ ] `resolveGenerationJob` polls until `succeeded`
- [ ] Parameters panel reflects updated value
- [ ] CAD viewer loads new version

## 3. Chat: modify_selected_part

- [ ] Select a part (e.g. part:fuselage) in CAD viewer
- [ ] Send "加长2米"
- [ ] SSE event `generation_started` received with `job_id`
- [ ] `resolveGenerationJob` polls until `succeeded`
- [ ] Selected part reflects change in parameters and viewer

## 4. ParameterPanel PATCH

- [ ] Modify a parameter in ParameterPanel
- [ ] Click apply
- [ ] PATCH request sent to `/api/designs/{id}/spec`
- [ ] Response contains `job_id` with `status: "queued"`
- [ ] `pollJobToCompletion` resolves (skip-poll if already succeeded, else polls)
- [ ] `loadVersion` + `fetchVersionList` update UI
- [ ] Tool card shows completed state

## 5. Failed job handling

- [ ] Trigger a generation that will fail (e.g. set CAD_BACKEND to failing mode)
- [ ] `resolveGenerationJob` throws with error message
- [ ] Tool card shows ✗ icon with red border (tool-card-failed)
- [ ] Error message displayed to user via tool card fail state
- [ ] Failed version does NOT appear in version list
- [ ] GET /api/jobs/{id}/diagnostics returns error details

## 6. Failed job diagnostics

- [ ] Failed tool card shows "▸ 查看诊断" button (via DiagnosticsPanel component)
- [ ] Click "查看诊断" → DiagnosticsPanel fetches /api/jobs/{job_id}/diagnostics
- [ ] Diagnostics JSON displayed in expandable `<pre>` section
- [ ] Response includes: job, version_status, generation_log, validation_report, files_exist
- [ ] If generation_log or validation_report missing → shown as null
- [ ] Click "▾ 收起诊断" collapses the section
- [ ] Diagnostics fetch returns null on network error (no crash)
- [ ] When diagnostics data is null (404/network error) → "诊断信息暂不可用" displayed
- [ ] jobId is URL-encoded in diagnostics fetch request

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

## 9. generationFlow polling

- [ ] `pollJobToCompletion` with `initialStatus="succeeded"` skips polling (no /api/jobs call)
- [ ] `pollJobToCompletion` with `initialStatus="queued"` or `"running"` polls via resolveGenerationJob
- [ ] `resolveGenerationJob` throws "缺少 job_id" when jobId is empty
- [ ] `pollJobToCompletion` throws "缺少 job_id" when jobId is empty (even if succeeded)
- [ ] Files: `Record<string, string>` input converted to `string[]` output
- [ ] `error_message` propagated through when already succeeded
- [ ] `status` field typed as `JobStatus` (not `string`)

## 10. Missing job_id error prompt

- [ ] Chat SSE event with empty job_id does not crash
- [ ] resolveGenerationJob throws with clear "缺少 job_id" message
- [ ] Tool card shows error state with the message
- [ ] No unhandled promise rejection in console

## 11. Polling timeout

- [ ] Job polling respects maxAttempts (default 120) and intervalMs (default 1000ms)
- [ ] After maxAttempts exhausted, "生成任务超时" error thrown
- [ ] Tool card shows timeout error in fail state
- [ ] No infinite polling loop

## Manual Browser QA

### Setup
1. Start backend: `CAD_BACKEND=fake .venv/bin/python -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 3901`
2. Start frontend: `cd apps/web && npm run dev`
3. Open http://localhost:3900

### Test Sequence
1. **Happy path**: Design → Generate → Modify → Version switch
2. **Error path**: Open Settings → set cad_backend to failing → Generate → Verify diagnostics via DiagnosticsPanel
3. **Reset**: Settings → set cad_backend back to fake → Verify normal operation
4. **Concurrency**: Rapid-fire "generate" 3-4 times → Check version numbers are sequential
5. **Browser DevTools**: Network tab → verify polling requests to /api/jobs/{id} stop after succeeded/failed
6. **Missing job_id**: Inspect SSE events → verify empty job_id is handled gracefully
