# VSPAERO Multi-Surface Analysis + Deep Design Layout-Aware Strategies

**Date**: 2026-05-25
**Status**: Approved
**Scope**: Two independent subsystems — VSPAERO analysis and Deep Design variant generation

---

## Problem

All 11 aerodynamic layouts pass OpenVSP E2E, but two analysis/exploration subsystems treat every layout identically:

1. **VSPAERO** only analyzes the main wing. For multi-surface layouts (canard, biplane, tandem_wing), the aerodynamic interaction between surfaces is not captured.
2. **Deep Design** only varies `wing.span` when generating variants. Layout-specific fields (`canard.span`, `rear_wing.chord`, `second_wing.gap`) are never varied.

## Approach

Layered extension (Plan B): preserve existing interfaces, add a layout-aware layer on top of each subsystem.

---

## Part 1: VSPAERO Multi-Surface Analysis

### Current

`run_vspaero_analysis(adapter, spec, wing_geom_id)` adds only `main_wing` to the analysis Set.

### New Function: `build_analysis_geoms`

```python
def build_analysis_geoms(spec: AircraftSpec, build_results: list[BuildResult]) -> list[str]:
```

Returns a list of geometry IDs to include in the VSPAERO analysis set, based on layout:

| Layout | Geometries analyzed |
|--------|-------------------|
| conventional | main_wing |
| twin_boom | main_wing |
| flying_wing | main_wing |
| blended_wing_body | main_wing |
| canard | main_wing, canard |
| three_surface | main_wing, canard |
| tandem_wing | main_wing, rear_wing |
| biplane | main_wing, lower_wing |
| joined_wing | main_wing, rear_wing |
| box_wing | main_wing, lower_wing |
| multi_fuselage | main_wing |

Logic: extract layout from `spec.aircraft.layout`, look up each layout's extra geometry names, resolve names to geom_ids from `build_results`.

### Modified Function Signature

```python
def run_vspaero_analysis(
    adapter: OpenVspAdapter,
    spec: AircraftSpec,
    geom_ids: list[str],          # was: wing_geom_id: str
    *,
    alpha_range: tuple[float, float] = (-4.0, 12.0),
    alpha_step: float = 1.0,
    mach: float | None = None,
    output_dir: Path | None = None,
) -> VspaeroReport
```

All IDs in `geom_ids` are added to the same Set. VSPAERO computes the combined aerodynamic characteristics.

### Output Change

`VspaeroReport` gains one field:
- `components_analyzed: list[str]` — e.g. `["main_wing", "canard"]`

All existing fields (CL/CD/CM vs alpha, optimal L/D, CL_alpha, CD0) remain unchanged. They now reflect the combined multi-surface aerodynamics rather than wing-only.

### Caller Change

`backend.py` changes from:
```python
wing_geom_id = components.get("main_wing", "")
run_vspaero_analysis(adapter, spec, wing_geom_id, ...)
```
to:
```python
geom_ids = build_analysis_geoms(spec, results)
run_vspaero_analysis(adapter, spec, geom_ids, ...)
```

### Files Modified

| File | Change |
|------|--------|
| `services/workers/cad_worker/openvsp_generator/vspaero_analysis.py` | Add `build_analysis_geoms()`, change `run_vspaero_analysis()` signature |
| `services/workers/cad_worker/openvsp_generator/backend.py` | Update caller |

---

## Part 2: Deep Design Layout-Aware Strategies

### Current

`DEFAULT_STRATEGIES` has 3 fixed strategies (compact/standard/extended), each varying only `wing.span.value` by ±2m.

### New: `LAYOUT_STRATEGIES` Dictionary

```python
LAYOUT_STRATEGIES: dict[str, list[dict]] = {
    "conventional": DEFAULT_STRATEGIES,  # unchanged fallback
    "canard": [
        {"label": "compact",  "changes": [
            {"path": "wing.span.value", "value": -2, "op": "relative"},
            {"path": "canard.span.value", "value": -0.5, "op": "relative"},
        ]},
        {"label": "standard", "changes": []},
        {"label": "extended", "changes": [
            {"path": "wing.span.value", "value": 2, "op": "relative"},
            {"path": "canard.span.value", "value": 0.5, "op": "relative"},
        ]},
    ],
    "three_surface": [  # same as canard
        # wing.span ±2, canard.span ±0.5
    ],
    "tandem_wing": [
        # wing.span ±2, rear_wing.span ±1
    ],
    "joined_wing": [
        # wing.span ±2, rear_wing.span ±1
    ],
    "biplane": [
        # wing.span ±2, second_wing.gap ±0.2
    ],
    "box_wing": [
        # wing.span ±2, box_wing_config.gap ±0.3
    ],
    "twin_boom": DEFAULT_STRATEGIES,
    "flying_wing": DEFAULT_STRATEGIES,
    "blended_wing_body": DEFAULT_STRATEGIES,
    "multi_fuselage": DEFAULT_STRATEGIES,
}
```

Strategy selection rule: layouts with extra aerodynamic surfaces get multi-dimensional strategies; layouts where only wing span matters fall back to `DEFAULT_STRATEGIES`.

### Modified: `prepare_variants`

```python
def prepare_variants(state):
    base_spec = state["base_spec"]
    layout = base_spec.get("aircraft", {}).get("layout", "conventional")
    strategies = LAYOUT_STRATEGIES.get(layout, LAYOUT_STRATEGIES["conventional"])
    # ... rest of existing logic, using strategies instead of DEFAULT_STRATEGIES
```

### Files Modified

| File | Change |
|------|--------|
| `services/api/app/graph/deep_design_graph.py` | Add `LAYOUT_STRATEGIES`, modify `prepare_variants` |

---

## Testing

### VSPAERO Tests (in `tests/api/test_vspaero_analysis.py`)

- `test_build_analysis_geoms_conventional` → returns ["main_wing"]
- `test_build_analysis_geoms_canard` → returns ["main_wing", "canard"]
- `test_build_analysis_geoms_biplane` → returns ["main_wing", "lower_wing"]
- `test_build_analysis_geoms_tandem_wing` → returns ["main_wing", "rear_wing"]
- `test_build_analysis_geoms_flying_wing` → returns ["main_wing"]
- Cover all 11 layouts

### Deep Design Tests (in `tests/api/test_layout_builders.py`)

- `test_layout_strategy_canard_compact` → wing.span -2 and canard.span -0.5
- `test_layout_strategy_biplane_extended` → wing.span +2 and second_wing.gap +0.2
- `test_layout_strategy_fallback_unknown` → falls back to conventional strategies
- Verify patched specs contain correct layout-specific field changes

No new OpenVSP integration tests required (VSPAERO analysis is environment-dependent).

---

## Backward Compatibility

- `VspaeroReport.components_analyzed` is a new optional field; frontend ignores if absent
- Deep Design strategy change is backend-only; frontend still shows compact/standard/extended labels
- Conventional layout behavior is unchanged
- Existing tests continue to pass

---

## Out of Scope

- Per-surface aerodynamic reports (VSPAERO outputs combined metrics only)
- User-configurable variant parameters in the UI
- VSPAERO analysis for non-wing geometries (fuselage, booms, body)
- Constraint-based optimization in Deep Design
