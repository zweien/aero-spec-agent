# Graph Observability Dashboard Design

**Status:** Design document — implementation deferred.

## Overview

A monitoring dashboard for the LangGraph gray-release, tracking fallback rates, shadow divergence, graph latency, and CompareGraph runtime across all three modes (legacy / shadow / partial).

## Metrics

### 1. Fallback Rate

**Definition:** Percentage of partial mode requests that fall back to legacy.

```
fallback_rate = fallback_count / partial_requests_total
```

**Collection points:**
- `chat.py:_chat_partial` exception handler → log `partial graph failed, falling back to legacy`
- `design_controller.py:_compare_with_graph` exception handler → log `CompareGraph failed, falling back`

**Target:** < 1% in Phase 2 (partial mode)

**Alert:** Fallback rate > 5% for 10 consecutive minutes

### 2. Shadow Divergence

**Definition:** Percentage of shadow mode requests where old intent ≠ new intent.

```
divergence_rate = divergence_count / shadow_requests_total
```

**Source:** `storage/shadow_logs/*.jsonl` — count entries where `mismatches` is non-empty

**Target:** < 5% over 100+ conversations (Phase 1 exit criteria)

**Dashboard display:**
- Time series: divergence rate per hour
- Top mismatched intents (old vs new)

### 3. Graph Latency

**Definition:** End-to-end time from `graph.invoke()` call to result return.

**Collection:**
- Instrument `partial_graph.build_partial_design_graph` with timing decorator
- Log `graph_duration_ms` in structured logging

**Breakdown by node:**
- `classify_intent`: expected < 5ms
- `prepare_tool_args`: expected < 10ms
- `enqueue_job`: expected < 50ms
- `wait_for_job_event`: variable (depends on CAD generation)
- `emit_sse`: expected < 5ms

**Target:** Non-CAD nodes < 100ms total

### 4. CompareGraph Runtime

**Definition:** Time from `dispatch_variants` to `synthesize_summary` completion.

**Collection:**
- Instrument `compare_graph.build_compare_graph` with timing
- Log per-variant job duration

**Dashboard display:**
- P50/P90/P99 latency
- Variant count vs total runtime scatter plot

### 5. Partial Success Rate

**Definition:** Percentage of partial mode requests that produce valid SSE events.

```
success_rate = sse_produced_count / partial_requests_total
```

**Collection:**
- `chat.py:_chat_partial` → count when `sse_events` is non-empty
- Count `generation_started` events produced

**Target:** > 99% in partial mode

### 6. Job Lifecycle Events

**Definition:** Event flow completeness per job.

**Collection:**
- `job_events.py` bus → track per job: started → progress → completed/failed
- Flag jobs with missing events (started but no completed/failed)

**Dashboard display:**
- Event flow completion rate
- Average job duration (started → completed)

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  AeroSpec Graph Observability                                    │
├──────────────────┬──────────────────┬───────────────────────────┤
│  Fallback Rate   │ Shadow Divergence│ Partial Success Rate      │
│  ┌────────────┐  │ ┌──────────────┐ │ ┌───────────────────────┐ │
│  │   0.3%     │  │ │   2.1%       │ │ │   99.7%              │ │
│  │   ▁▃▂▁▁▃  │  │ │   ▂▃▁▂▁▃    │ │ │   ▅▇▇▇▇▇▇▇▇         │ │
│  └────────────┘  │ └──────────────┘ │ └───────────────────────┘ │
├──────────────────┴──────────────────┴───────────────────────────┤
│  Graph Latency (ms)                                              │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ classify_intent ▏▏ prepare ▏▏ enqueue ▏▏▏▏ wait ▏▏▏▏▏▏▏▏  ││
│  │     2ms              5ms        30ms        varies          ││
│  └─────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────┤
│  CompareGraph Runtime                                            │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  2 variants: 4.2s  │  3 variants: 6.8s  │  4 variants: 9s ││
│  └─────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────┤
│  Job Lifecycle Events                                            │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Last hour: 142 jobs                                       ││
│  │  started: 142  completed: 139  failed: 3  missing: 0       ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Implementation Approach

### Option A: Structured Logging + Grafana

- Add structured JSON logging to each graph node
- Ship logs to Grafana via Loki or similar
- Build Grafana dashboard panels

### Option B: LangSmith Traces

- Use existing `get_tracing_config()` with `LANGCHAIN_TRACING_V2=true`
- LangSmith provides per-node latency, error tracking, and run history
- No custom dashboard needed — LangSmith UI handles it

### Option C: Custom Metrics Endpoint

- Add `/api/metrics` endpoint exposing Prometheus-format metrics
- Counters: `partial_requests_total`, `fallback_total`, `sse_produced_total`
- Histograms: `graph_duration_ms`, `compare_graph_duration_ms`
- Gauges: `shadow_divergence_rate`, `active_jobs`

**Recommendation:** Start with Option B (LangSmith), add Option A for production monitoring.

## Data Collection Implementation Sketch

```python
# services/api/app/graph/observability.py

import logging
import time
from functools import wraps

logger = logging.getLogger("graph.observability")

def observe_node(node_name: str):
    """Decorator that logs node execution time and status."""
    def decorator(func):
        @wraps(func)
        def wrapper(state):
            start = time.monotonic()
            try:
                result = func(state)
                duration_ms = (time.monotonic() - start) * 1000
                logger.info(
                    "node_completed",
                    extra={
                        "node": node_name,
                        "duration_ms": round(duration_ms, 1),
                        "status": result.get("status", "ok"),
                    },
                )
                return result
            except Exception as e:
                duration_ms = (time.monotonic() - start) * 1000
                logger.error(
                    "node_failed",
                    extra={
                        "node": node_name,
                        "duration_ms": round(duration_ms, 1),
                        "error": str(e),
                    },
                )
                raise
        return wrapper
    return decorator
```

## Rollout Monitoring Checklist

- [ ] LangSmith project configured for `aero-spec-agent`
- [ ] Structured logging added to all graph nodes
- [ ] Fallback rate tracked in logs
- [ ] Shadow divergence rate calculated from shadow_logs/
- [ ] CompareGraph runtime logged per invocation
- [ ] Job lifecycle event completion rate monitored
- [ ] Alerting configured for fallback > 5%
