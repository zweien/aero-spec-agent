# Deep Agents Runtime Plan

**Status:** Draft — design only, no implementation yet.

## Overview

`/api/deep-design` is a future endpoint that orchestrates multi-variant aircraft design exploration using LangGraph Deep Agents. It automates the iterative design loop: explore variants → evaluate → optimize → synthesize report.

## Architecture

```
POST /api/deep-design
  → DeepDesignGraph
    ├── explore_variants: fan-out N design variants
    ├── evaluate_results: assess each variant via engineering metrics
    ├── optimize_loop: iterate on best candidates (max K rounds)
    └── synthesize_report: generate comparison report

GET /api/deep-design/{id}
  → Status + intermediate results + final report
```

## Graph Flow

```
START
  → parse_requirements (extract design constraints from natural language)
  → generate_base_spec (create initial AircraftSpec via LLM)
  → explore_variants (fan-out: dispatch N variant specs)
  → evaluate_results (collect results, score each variant)
  → optimization_needed? (conditional)
      → yes: refine_variants → explore_variants (loop back, max K iterations)
      → no: synthesize_report
  → END
```

## Nodes

### parse_requirements
- Input: `user_description: str`, `constraints: dict`
- Output: parsed design requirements (range, payload, speed, etc.)
- Uses LLM to extract structured parameters from natural language

### generate_base_spec
- Input: parsed requirements
- Output: `AircraftSpec` base configuration
- Generates initial spec meeting all hard constraints

### explore_variants
- Input: base spec + variant strategies
- Output: N dispatched generation jobs (reuses CompareGraph dispatch)
- Strategies: parameter sweep, topology variation, constraint relaxation

### evaluate_results
- Input: variant generation results
- Output: scored variants with metrics
- Metrics: structural weight, range estimate, stability margin, manufacturability

### refine_variants
- Input: scored variants, iteration count
- Output: refined specs for next round
- Modifies parameters of top-K variants to improve scores

### synthesize_report
- Input: all variant results, scores, iteration history
- Output: markdown report with comparison table, recommendations

## State Schema

```python
class DeepDesignState(TypedDict):
    # Input
    user_description: str
    constraints: dict[str, Any]

    # Parsed
    requirements: dict[str, Any]

    # Base spec
    base_spec: dict[str, Any] | None

    # Iteration tracking
    iteration: int
    max_iterations: int  # default 3

    # Variants
    variant_strategies: list[dict[str, Any]]
    variant_jobs: Annotated[list[dict], operator.add]
    variant_scores: list[dict[str, Any]]

    # Results
    best_variant: dict[str, Any] | None
    report: str
    status: str
```

## API Contract

### POST /api/deep-design

```json
{
  "description": "设计一架长航时侦察无人机，航程500km，载荷10kg",
  "constraints": {
    "max_iterations": 3,
    "variant_count": 4
  }
}
```

Response:
```json
{
  "id": "dd-abc123",
  "status": "running",
  "iteration": 0,
  "message": "Deep design exploration started"
}
```

### GET /api/deep-design/{id}

```json
{
  "id": "dd-abc123",
  "status": "completed",
  "iteration": 2,
  "best_variant": { ... },
  "report": "# Design Exploration Report\n...",
  "variant_history": [ ... ]
}
```

## Integration Points

- **CompareGraph**: `explore_variants` reuses `dispatch_variants` node
- **JobRunner**: Same job lifecycle management
- **JobEventBus**: Event-driven progress streaming
- **SSE Adapter**: Stream progress to frontend

## Frontend Requirements

- New `DeepDesignPanel` component
- Progress indicator showing iteration/variant status
- Report viewer with markdown rendering
- 3D comparison of top variants

## Rollout Strategy

1. Phase 1: Single-iteration mode (no optimization loop)
2. Phase 2: Multi-iteration with user review between rounds
3. Phase 3: Fully autonomous optimization with configurable limits

## Risks

- LLM cost: multiple spec generation calls per iteration
- Latency: N variants × M iterations can take minutes
- Quality: automated evaluation may miss domain-specific criteria
- Scope creep: must constrain variant space to avoid combinatorial explosion
