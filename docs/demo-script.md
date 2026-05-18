# AeroSpec Demo Script

## Prerequisites

```bash
# Terminal 1 — Backend (fake CAD backend)
cd /path/to/aero-spec-agent
set -a && . ./.env && set +a
CAD_BACKEND=fake .venv/bin/python -m uvicorn services.api.app.main:app --host "$API_HOST" --port "$API_PORT"

# Terminal 2 — Frontend
cd /path/to/aero-spec-agent/apps/web
set -a && . ../../.env && set +a
npm run dev
```

Open http://localhost:3900

---

## Demo 1: Natural Language Generation

**Goal:** Generate an aircraft design from natural language.

1. In the chat input, type:

   > 设计一架翼展12米的双发无人机，巡航速度200km/h，起飞重量150kg

2. **Expected behavior:**
   - SSE stream shows assistant response with design reasoning
   - `generation_started` event fires with `job_id`
   - Tool card appears with spinner ("正在生成 CAD 模型...")
   - Polling resolves to `succeeded`
   - Tool card transitions to done (✓) with version number (e.g. v1)
   - CAD viewer loads the 3D preview
   - Parameter panel populates with spec values
   - Version panel shows v1

3. **Verify in Network tab:**
   - POST /api/chat → SSE stream
   - GET /api/jobs/{id} polling requests (stop after succeeded)
   - GET /api/designs/{id}/versions/1/files/aircraft.glb

---

## Demo 2: Parameter Modification

**Goal:** Modify a parameter via chat and via ParameterPanel.

### Chat-based modification

1. Type:

   > 把翼展改成15米

2. **Expected behavior:**
   - New generation triggered
   - Tool card shows v2
   - CAD viewer updates
   - Wing span in ParameterPanel reflects 15m

### ParameterPanel modification

1. In ParameterPanel, find a numeric field (e.g. wing span)
2. Change the value
3. Click "Apply" (待应用 changes badge shows count)
4. **Expected behavior:**
   - PATCH /api/designs/{id}/spec sent
   - Job polling resolves
   - New version created (v3)
   - Tool card shows completed state

---

## Demo 3: Selected Part Modification

**Goal:** Select a part in the CAD viewer and modify it.

1. Click on a visible part in the 3D viewer (e.g. fuselage or wing)
2. The part highlights; its ref appears as selected
3. Type in chat:

   > 加长2米

4. **Expected behavior:**
   - Modification targets the selected part
   - New version generated with the change applied to that part only

---

## Demo 4: Failed Job Diagnostics

**Goal:** Trigger a failed generation and view diagnostics.

### Method: Use a malformed spec

1. If using fake backend, the following approaches can trigger failures:
   - Send a chat message that produces an extremely malformed spec
   - Or configure the backend to fail (modify fake backend temporarily)

2. **Expected behavior when a job fails:**
   - Tool card shows ✗ icon with red border (`tool-card-failed`)
   - Error message displayed in tool card
   - "▸ 查看诊断" button visible

3. Click "▸ 查看诊断"

4. **Expected behavior:**
   - Button text changes to "加载中..." briefly
   - GET /api/jobs/{job_id}/diagnostics request fires
   - Diagnostics JSON expands in a `<pre>` block
   - JSON includes: `job`, `version_status`, `generation_log`, `validation_report`, `files_exist`
   - If some fields are missing → shown as `null`

5. Click "▾ 收起诊断" → section collapses

6. If diagnostics unavailable (e.g. job data deleted):
   - "诊断信息暂不可用" message displayed

### Verify version list

- Failed versions do NOT appear in VersionPanel
- Only succeeded versions shown

---

## Demo 5: Version History

1. After multiple generations, open VersionPanel
2. Click on a previous version → CAD viewer and parameters update
3. Version numbers are sequential for succeeded versions (skip failed)

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| CSS/JS 404 after changes | `rm -rf apps/web/.next && npm run dev` |
| Port 8900 occupied | `fuser -k 8900/tcp` |
| Port 3900 occupied | `fuser -k 3900/tcp` |
| Backend import error | Check `.env` and `CAD_BACKEND=fake` |
