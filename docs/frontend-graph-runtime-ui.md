# GraphExecutionPanel — Frontend Design

## Overview

GraphExecutionPanel displays real-time graph execution state for the LangGraph runtime,
including node timeline, variant status, event streaming, and CompareGraph visualization.

## Components

### 1. GraphNodeTimeline

Displays graph execution as a horizontal timeline with node states.

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ parse_   │──▶│ prepare_ │──▶│ run_     │──▶│ synthesize│
│ require- │   │ variants │   │ compare  │   │ _report  │
│ ments    │   │          │   │          │   │          │
│  ✓ 45ms │   │  ✓ 12ms  │   │  ⏳ ...  │   │    ·     │
└──────────┘   └──────────┘   └──────────┘   └──────────┘
```

States: `pending` (gray), `running` (blue pulse), `completed` (green), `failed` (red).

Data source: `observe_node` structured logs via SSE `graph_node` event type.

### 2. VariantRuntimeStatus

Shows all dispatched variants with individual job lifecycle status.

```
┌─────────────────────────────────────────────────┐
│  Variant  │  Status    │  Duration │  Actions   │
│───────────│────────────│───────────│────────────│
│  compact  │  ✓ done    │  1.2s     │  [View]    │
│  standard │  ⟳ running │  0.8s ... │  [Cancel]  │
│  extended │  ○ queued  │  -        │  -         │
└─────────────────────────────────────────────────┘
```

Data source: JobEventBus SSE events (`generation_started`, `generation_progress`,
`generation_complete`, `generation_failed`).

### 3. EventStreamViewer

Scrollable log of all runtime events with filtering.

```
[12:34:56.789] generation_started    job=abc123  variant=compact
[12:34:57.123] generation_progress   job=abc123  step=mesh_export  progress=60%
[12:34:58.456] generation_complete   job=abc123  duration=1667ms
[12:34:58.789] generation_started    job=def456  variant=standard
```

Filter options: event type, variant label, time range.

### 4. CompareGraphVisualization

Side-by-side comparison of variant results.

```
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│   compact     │  │   standard    │  │   extended    │
│               │  │               │  │               │
│  [3D Preview] │  │  [3D Preview] │  │  [3D Preview] │
│               │  │               │  │               │
│  Span: 10m    │  │  Span: 12m    │  │  Span: 14m    │
│  Weight: 45kg │  │  Weight: 50kg │  │  Weight: 55kg │
│  ★ Recommended│  │               │  │               │
└───────────────┘  └───────────────┘  └───────────────┘
```

Highlights the recommended variant (fastest successful).

## SSE Event Schema

### graph_node event
```json
{
  "event_type": "graph_node",
  "node": "explore_variants",
  "latency_ms": 45.2,
  "input_keys": ["base_spec", "design_id"],
  "output_keys": ["variant_jobs", "status"],
  "status": "ok"
}
```

### generation_progress event (enhanced)
```json
{
  "event_type": "generation_progress",
  "job_id": "abc123",
  "design_id": "my-design",
  "current_step": "mesh_export",
  "progress": 60,
  "steps_total": 4,
  "steps_completed": 2
}
```

## Implementation Notes

- Use React components with Framer Motion for node state transitions
- GraphNodeTimeline subscribes to `graph_node` SSE events
- VariantRuntimeStatus subscribes to `generation_*` SSE events
- EventStreamViewer is a virtualized list (react-window or similar)
- CompareGraphVisualization loads GLB previews per variant via `/api/designs/{id}/versions/{no}/files/aircraft.glb`

## API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `GET /api/jobs/{id}` | Poll variant job status |
| `GET /api/designs/{id}/versions/{no}/files/{name}` | Fetch GLB previews |
| `POST /api/chat/stream` | SSE event stream for node + job events |
| `POST /api/deep-design` | Trigger multi-variant exploration |
