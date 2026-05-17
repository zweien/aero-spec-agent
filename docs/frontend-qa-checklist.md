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
