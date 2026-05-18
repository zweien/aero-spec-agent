# Graph Mode Rollout Strategy

## Overview

The chat endpoint (`/api/chat`) supports three modes controlled by `CHAT_GRAPH_MODE`:

| Mode | Behavior | Risk |
|------|----------|------|
| `legacy` | Existing ChatService only | Zero (default) |
| `shadow` | Legacy ChatService + LangGraph shadow classification + divergence logging | Zero (read-only side effect) |
| `partial` | LangGraph partial graph with fallback to legacy | Low (fallback on any error) |

## Mode Details

### legacy (default)

```
User → /api/chat → ChatService.chat_stream() → SSE events
```

No graph involvement. This is the production-safe default.

### shadow

```
User → /api/chat → ChatService.chat_stream() → SSE events (to user)
                  → LangGraph shadow classification → shadow_logs/ (side channel)
```

Both paths run. The old ChatService streams to the user as usual.
The LangGraph path classifies intent and logs divergence to `storage/shadow_logs/`.
No impact on user-facing behavior.

Divergence log fields:
- `conversation_id`, `user_message`
- `old_result.intent`, `new_result.intent`, `new_result.tool_name`

### partial

```
User → /api/chat → LangGraph partial graph → SSE events (generation_started only)
                  → Fallback to legacy on any error
```

The partial graph runs in API-safe mode (`observe_until_terminal=False`):
1. Classifies intent
2. Validates and enqueues job via JobRunner
3. Returns `generation_started` SSE event immediately
4. Client polls `/api/jobs/{id}` for completion

**Fallback:** Any exception in the graph path falls back to the legacy ChatService stream.

## Rollout Plan

### Phase 1: Shadow (current)

```bash
CHAT_GRAPH_MODE=shadow
```

- Run for 2+ weeks
- Monitor `storage/shadow_logs/` for divergence rate
- Exit criteria: divergence < 5% over 100+ conversations

### Phase 2: Partial (gray release)

```bash
CHAT_GRAPH_MODE=partial
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=aero-spec-agent-partial
```

- Enable for a subset of users (canary)
- Monitor LangSmith traces for errors and latency
- Monitor `/api/jobs/{id}` poll success rate
- Exit criteria: < 1% fallback rate over 500+ requests

### Phase 3: Main (full migration)

```bash
CHAT_GRAPH_MODE=partial  # Eventually becomes the default
```

- CompareGraph replaces DesignControllerService
- SSE adapter becomes the primary output path
- Legacy code retained but no longer exercised in production

## Rollback

Set `CHAT_GRAPH_MODE=legacy` in the environment and restart the API server.
No database migration or code change required.

## DesignController Integration

`/api/design-controller/compare` uses CompareGraph when `CHAT_GRAPH_MODE` is `partial` or `shadow`:

```
POST /compare
  → CompareGraph.dispatch_variants (N variant jobs)
  → Background tasks run each job
  → Returns ControllerJob (same API contract)
```

The `GET /{id}` endpoint still uses `DesignControllerService.aggregate()` for result collection.

## LangSmith Tracing

When `LANGCHAIN_TRACING_V2=true`:

- Graph invocations include metadata: `design_id`, `conversation_id`, `graph_mode`
- Node transitions are visible as spans
- SSE events are logged as outputs
- No impact when disabled (config returns empty dict)

## Monitoring Checklist

- [ ] `storage/shadow_logs/` divergence rate (shadow mode)
- [ ] LangSmith project `aero-spec-agent` trace volume
- [ ] `/api/jobs/{id}` poll latency and success rate
- [ ] Fallback rate in partial mode (check logs for "falling back to legacy")
- [ ] `storage/controller_jobs/` for CompareGraph job tracking
