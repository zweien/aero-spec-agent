# Deep Agents Design Controller

## Goal

A parallel orchestration layer that explores multiple design alternatives, compares versions, generates reports, and summarizes failure diagnostics — without replacing the existing `/api/chat` endpoint.

## Motivation

The current chat flow produces one design at a time. For concept design exploration, users benefit from:

- **Multi-variant generation**: Generate 3+ wing configurations simultaneously, compare aerodynamic performance
- **Automated trade studies**: "Compare a 12m vs 15m wing span for this fuselage"
- **Failure diagnosis summaries**: "Why did v3 fail? Summarize all failed jobs"
- **Report generation**: Compile design history, validation rules, and aero analysis into a structured report

These capabilities require a controller that can dispatch multiple jobs, aggregate results, and synthesize — beyond the linear chat flow.

## Architecture

```
┌─────────────────────────────────────────┐
│  /api/chat (existing, unchanged)         │
│  ChatService → single tool execution     │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  /api/design-controller (new)            │
│  DesignController                        │
│                                          │
│  ┌─────────────────────────────────┐    │
│  │  Plan Decomposer                │    │
│  │  "Compare 3 wing configs"       │    │
│  │  → [variant_a, variant_b, ...]  │    │
│  └──────────────┬──────────────────┘    │
│                 │                        │
│  ┌──────────────▼──────────────────┐    │
│  │  Job Dispatcher                 │    │
│  │  enqueue_generate per variant   │    │
│  │  (reuses existing JobRunner)    │    │
│  └──────────────┬──────────────────┘    │
│                 │                        │
│  ┌──────────────▼──────────────────┐    │
│  │  Result Aggregator              │    │
│  │  collect jobs → compare table   │    │
│  └──────────────┬──────────────────┘    │
│                 │                        │
│  ┌──────────────▼──────────────────┐    │
│  │  Report Synthesizer (LLM)       │    │
│  │  structured report + comparison │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

## API Endpoints

### POST /api/design-controller/compare

Request:
```json
{
  "design_id": "demo",
  "base_version": 1,
  "variants": [
    {"path": "wing.span.value", "value": 12},
    {"path": "wing.span.value", "value": 15},
    {"path": "wing.span.value", "value": 18}
  ]
}
```

Response (async):
```json
{
  "controller_job_id": "ctl-abc123",
  "status": "running",
  "variants": [
    {"label": "12m span", "job_id": "..."},
    {"label": "15m span", "job_id": "..."},
    {"label": "18m span", "job_id": "..."}
  ]
}
```

### GET /api/design-controller/{controller_job_id}

Returns aggregated results when all variant jobs complete:
```json
{
  "status": "completed",
  "comparison": {
    "variants": [
      {
        "label": "12m span",
        "version_no": 2,
        "status": "succeeded",
        "validation": {"rules_pass": 8, "rules_fail": 0},
        "vspaero": {"optimal_ld": 12.3, "cd0": 0.028}
      },
      ...
    ],
    "summary": "LLM-generated comparison text",
    "recommendation": "15m variant offers best L/D ratio..."
  }
}
```

### POST /api/design-controller/diagnose-failures

Request:
```json
{"design_id": "demo"}
```

Collects all failed jobs, fetches diagnostics, and produces an LLM summary:
```json
{
  "total_failed": 3,
  "summaries": [
    {
      "version_no": 3,
      "job_id": "...",
      "error": "cad backend crashed",
      "diagnosis": "The wing span of 25m exceeds the fuselage structural limit..."
    }
  ]
}
```

### POST /api/design-controller/report

Request:
```json
{"design_id": "demo", "include_vspaero": true}
```

Generates a structured design report across all succeeded versions.

## Implementation

### Phase 1: Job Dispatcher + Aggregator

- `DesignControllerService` in `services/api/app/services/design_controller.py`
- `ControllerJob` dataclass: id, design_id, status, variant_jobs, results
- Reuses existing `JobRunner` for each variant
- Polls variant jobs until all terminal
- Returns raw comparison data (no LLM synthesis yet)

### Phase 2: Report Synthesizer

- LLM call with aggregated results as context
- Structured prompt for comparison/recommendation
- SSE streaming for report generation progress

### Phase 3: Failure Diagnoser

- Scans all failed jobs for a design_id
- Fetches diagnostics for each
- LLM summarizes common failure patterns and root causes

## Frontend Integration

Not in the initial scope. The design controller is an API-only feature. Future frontend could add:
- "Compare variants" panel in VersionPanel
- Comparison table view
- Report viewer

## Concurrency Model

- Variant jobs run in parallel (each gets its own version_no)
- `ControllerJob` tracks per-variant status
- Aggregation triggers when all variants reach terminal state
- Uses existing `BackgroundTasks` — no Celery/RQ needed for current scale

## Data Model

```
storage/
  controller_jobs/
    {controller_job_id}.json    — ControllerJob state
  designs/
    {design_id}/
      versions/
        {N}/                     — Each variant is a normal version
```

ControllerJob is a meta-layer over existing version storage. No schema changes to existing models.

## Testing

1. Unit: ControllerService with mocked JobRunner
2. Integration: full dispatch → aggregate cycle with FakeCadBackend
3. API: compare/diagnose/report endpoint contract tests
4. Concurrency: parallel variant dispatch produces unique version numbers
