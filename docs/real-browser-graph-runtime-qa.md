# Real Browser QA: Graph Runtime UI & API Endpoints

## Scope

Manual browser-based QA checklist for the graph runtime features added in Round 18.

**Prerequisites:**

```bash
# Terminal 1: Backend
cd /path/to/aero-spec-agent
set -a && . ./.env && set +a
CAD_BACKEND=fake .venv/bin/python -m uvicorn services.api.app.main:app --host "$API_HOST" --port "$API_PORT"

# Terminal 2: Frontend
cd apps/web
set -a && . ../../.env && set +a
npm run dev
```

---

## 1. /api/metrics Endpoint

### Steps

1. Open terminal, run:
   ```bash
   curl http://localhost:$API_PORT/api/metrics
   ```

### Expected

- Response is `text/plain` with Prometheus exposition format
- Contains `aerospec_requests_total 0` (or similar counters)
- HTTP 200

### After deep-design run

1. Trigger a deep-design request:
   ```bash
   curl -X POST http://localhost:$API_PORT/api/deep-design \
     -H 'Content-Type: application/json' \
     -d '{"design_id":"qa-test-1","description":"test UAV","base_spec":{},"constraints":{"variant_count":1}}'
   ```
2. Re-fetch `/api/metrics`
3. Verify counters incremented (e.g., `aerospec_deep_design_runs_total` increased)

---

## 2. /api/deep-design Endpoint

### Test Case 1: Basic 2-variant design

```bash
curl -X POST http://localhost:$API_PORT/api/deep-design \
  -H 'Content-Type: application/json' \
  -d '{
    "design_id": "qa-2v",
    "description": "设计一架长航时无人机",
    "base_spec": '"$(cat packages/aircraft-schema/examples/twin_engine_uav.yaml | python3 -c 'import sys,json,yaml; print(json.dumps(yaml.safe_load(sys.stdin)))')"' ,
    "constraints": {"variant_count": 2}
  }'
```

### Expected

- HTTP 200
- Response JSON has `status: "completed"`
- `comparison.total_variants === 2`
- `report` is a non-empty string containing markdown table
- `results` array has 2 entries, each with `label`, `status`, `thread_id`

### Test Case 2: Invalid spec (422)

```bash
curl -X POST http://localhost:$API_PORT/api/deep-design \
  -H 'Content-Type: application/json' \
  -d '{"design_id":"qa-null","description":"test","base_spec":null,"constraints":{}}'
```

### Expected

- HTTP 422 (Pydantic validation rejects null base_spec)

### Test Case 3: Single variant

```bash
curl -X POST http://localhost:$API_PORT/api/deep-design \
  -H 'Content-Type: application/json' \
  -d '{
    "design_id": "qa-1v",
    "description": "小型物流无人机",
    "base_spec": '"$(cat packages/aircraft-schema/examples/twin_engine_uav.yaml | python3 -c 'import sys,json,yaml; print(json.dumps(yaml.safe_load(sys.stdin)))')"' ,
    "constraints": {"variant_count": 1}
  }'
```

### Expected

- HTTP 200, `comparison.total_variants === 1`

---

## 3. GraphExecutionPanel Component (Visual)

### Steps

1. Open browser to `http://localhost:3900`
2. Navigate to a design page that triggers the graph runtime
3. Look for the GraphExecutionPanel section

### Expected Visual Elements

- **Node Timeline**: horizontal row of node cards with arrows between them
  - Completed nodes: green background with checkmark
  - Running nodes: blue background with pulse animation
  - Failed nodes: red background with X
  - Pending nodes: gray background with circle
  - Latency shown as "XXms" on completed nodes
- **Variant Status**: table with columns Variant / Status / Duration
  - Status text color-coded (green=succeeded, blue=running, red=failed)
- **Event Stream**: monospace log with timestamps
  - Events show `[HH:MM:SS] event_type job=abc12345 detail...`
  - Empty state shows "No events yet."
- **Section headings**: "Graph Execution Runtime", "Node Timeline", "Variant Status", "Event Stream"

### Note

Currently the panel uses mock/static data props. Real SSE binding is a future task.

---

## 4. /health Endpoint (Regression)

```bash
curl http://localhost:$API_PORT/health
```

### Expected

- HTTP 200, JSON with `status: "ok"`

---

## 5. Existing Features (Regression)

### Generation API

```bash
curl -X POST http://localhost:$API_PORT/api/designs/qa-regen/generate \
  -H 'Content-Type: application/yaml' \
  --data-binary @packages/aircraft-schema/examples/twin_engine_uav.yaml
```

### Expected

- HTTP 202, returns `job_id`
- Polling `/api/jobs/{job_id}` eventually returns `status: "succeeded"`

### Version History

```bash
curl http://localhost:$API_PORT/api/designs/qa-regen/versions
```

### Expected

- HTTP 200, list with at least one version

---

## QA Sign-off

| Item | Status | Notes |
|------|--------|-------|
| /api/metrics returns Prometheus text | | |
| /api/deep-design 2-variant completes | | |
| /api/deep-design null spec returns 422 | | |
| /api/deep-design 1-variant completes | | |
| GraphExecutionPanel renders correctly | | |
| /health returns ok | | |
| Generation API still works | | |
| Version history still works | | |
