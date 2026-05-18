# Graph Mode QA Report

**Date:** 2026-05-18
**HEAD:** 418fb3a → current
**Scope:** `/api/chat` graph mode switch (`CHAT_GRAPH_MODE=legacy|shadow|partial`)

---

## Test Matrix

| Mode | Endpoint | Input | Expected | Result |
|------|----------|-------|----------|--------|
| legacy | POST /api/chat | message="你好" | SSE text/event-stream via ChatService | PASS |
| shadow | POST /api/chat | message="生成一架无人机" | Legacy SSE + shadow_logs/*.jsonl | PASS |
| shadow | POST /api/chat | message="你好" | Legacy SSE + no divergence log | PASS |
| partial | POST /api/chat | spec=None + generate_design | Fallback to legacy SSE | PASS |
| partial | POST /api/chat | spec + generate_design | generation_started SSE | PASS |
| partial | POST /api/chat | spec + modify_design | generation_started SSE | PASS |
| partial | POST /api/chat | spec + selected_refs | generation_started SSE | PASS |
| partial | POST /api/chat | conversation intent | Fallback to legacy SSE | PASS |
| partial | POST /api/chat | graph crash exception | Fallback to legacy SSE | PASS |

---

## SSE Contract

### generation_started (partial mode)

```
event: generation_started
data: {"job_id":"<uuid>","status":"queued","version_no":1,"design_id":"...","created_at":"...","updated_at":"..."}
```

Frontend receives this and starts polling `GET /api/jobs/{job_id}`.

### message (partial mode, after SSE events)

```
event: message
data: {"content":"已提交生成任务，正在后台生成 CAD 模型。","intent":"generate_design","job_id":"...","status":"queued"}
```

Frontend displays the `content` field as an assistant message.

### generation_complete (legacy mode, after polling)

Frontend polls `GET /api/jobs/{job_id}` and receives:

```json
{
  "job_id": "<uuid>",
  "status": "succeeded",
  "version_no": 1,
  "design_id": "...",
  "files": ["aircraft_spec.yaml", "aircraft.vsp3", ...]
}
```

---

## Fallback Behavior

| Condition | Mode | Fallback | Verified |
|-----------|------|----------|----------|
| `current_spec=None` + `generate_design` | partial | Legacy ChatService (LLM needed) | PASS |
| Graph raises exception | partial | Legacy ChatService | PASS |
| `intent=conversation` | partial | Legacy ChatService (no tool call) | PASS |
| No SSE events produced | partial | Legacy ChatService | PASS |
| CompareGraph raises exception | partial | Legacy DesignControllerService | PASS |

---

## Shadow Logging

Shadow mode runs both old ChatService (user-facing) and LangGraph classification (side channel).

**Divergence log location:** `storage/shadow_logs/{conversation_id}.jsonl`

**Log format:**

```json
{
  "timestamp": "2026-05-18T13:00:00+00:00",
  "conversation_id": "...",
  "user_message": "...",
  "old": {"intent": "generate_design"},
  "new": {"intent": "generate_design", "tool_name": "generate_design"},
  "mismatches": []
}
```

When `mismatches` is empty, old and new agree. When non-empty, divergence detected.

---

## Job Polling (partial mode)

Partial mode uses `observe_until_terminal=False` (fire-and-forget):

1. Graph enqueues job via `JobRunner.enqueue_generate()`
2. Returns `generation_started` SSE immediately
3. Client polls `GET /api/jobs/{job_id}` for completion
4. No blocking — request completes in <100ms

---

## DesignController (CompareGraph)

| Endpoint | Mode | Flow | Verified |
|----------|------|------|----------|
| POST /compare | partial/shadow | CompareGraph dispatch → ControllerJob | PASS |
| POST /compare | legacy | DesignControllerService.compare_variants | PASS |
| GET /{id} | all | aggregate() polls variant job statuses | PASS |

**Aggregation guarantees:**
- No duplicate results on repeated calls
- Running jobs not appended to results until terminal
- Missing jobs marked as failed
- `completed` status only when all variants are terminal

---

## Test Coverage

### New tests (this round)

| File | Tests | Coverage |
|------|-------|----------|
| `test_chat_graph_mode_api.py` | 10 | legacy/shadow/partial SSE + fallback |
| `test_design_controller_graph_mode.py` | 9 | dispatch, aggregation, API endpoints |

### Existing tests (previous rounds)

| File | Tests | Coverage |
|------|-------|----------|
| `test_chat_graph_mode.py` | 8 | graph mode defaults, SSE contract |
| `test_compare_graph.py` | 7 | CompareGraph dispatch + aggregation |
| `test_graph_stabilization.py` | 15 | node unit tests, error propagation |
| `test_langgraph_partial_mode.py` | 14 | partial graph flow |
| `test_langgraph_shadow_runtime.py` | 8 | shadow classification |

---

## Frontend Compatibility

Partial mode SSE is designed to be drop-in compatible with the existing ChatPanel:

1. **generation_started**: Same format as legacy — triggers job polling
2. **message**: New `content` field — displayed as assistant message
3. **No generation_complete**: Client polls `/api/jobs/{id}` instead
4. **Fallback transparent**: If graph fails, legacy SSE is returned — no frontend change needed

---

## Rollout Checklist

- [x] `CHAT_GRAPH_MODE=legacy` — zero risk, default
- [x] `CHAT_GRAPH_MODE=shadow` — read-only side effect, logs to shadow_logs/
- [x] `CHAT_GRAPH_MODE=partial` — fire-and-forget, fallback on any error
- [x] SSE events match frontend contract
- [x] Fallback to legacy on all error paths
- [x] DesignController aggregate handles CompareGraph jobs
- [ ] Shadow divergence rate < 5% over 100+ conversations (Phase 1 exit criteria)
- [ ] Partial fallback rate < 1% over 500+ requests (Phase 2 exit criteria)
