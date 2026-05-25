# VSPAERO Multi-Surface Analysis + Deep Design Layout-Aware Strategies

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make VSPAERO analyze all aerodynamic surfaces for multi-surface layouts, and make Deep Design vary layout-specific fields when generating variants.

**Architecture:** Layered extension — add layout-aware layer on top of existing VSPAERO and Deep Design subsystems. `build_analysis_geoms()` maps layout to component names, resolves to geom IDs. `LAYOUT_STRATEGIES` maps layout to variant strategies with layout-specific field paths.

**Tech Stack:** Python 3.11+, pytest, dataclasses, Pydantic

**Spec:** `docs/superpowers/specs/2026-05-25-vspareo-deep-design-layout-aware-design.md`

---

## Files Modified

| File | Responsibility |
|------|---------------|
| `services/workers/cad_worker/openvsp_generator/vspaero_analysis.py` | Add `LAYOUT_ANALYSIS_NAMES`, `build_analysis_geoms()`, add `components_analyzed` to `VspaeroReport`, change `run_vspaero_analysis()` signature |
| `services/workers/cad_worker/openvsp_generator/backend.py` | Update VSPAERO caller to use `build_analysis_geoms` |
| `services/api/app/graph/deep_design_graph.py` | Add `LAYOUT_STRATEGIES`, modify `prepare_variants`, modify `refine_variants` |
| `tests/api/test_vspaero_analysis.py` | Add `TestBuildAnalysisGeoms` (11 tests), update `TestRunVspaeroHandlesError`, add `TestVspaeroReportComponentsAnalyzed` |
| `tests/api/test_layout_builders.py` | Add `TestLayoutStrategies`, `TestLayoutAwarePrepareVariants` |
| `docs/layout-maturity-matrix.md` | Update VSPAERO and Deep Design rows from ⚠️ to ✅ |

---

## Batch 1: VSPAERO Multi-Surface Analysis

### Task 1: `build_analysis_geoms` function + tests for all 11 layouts

**Files:**
- Modify: `services/workers/cad_worker/openvsp_generator/vspaero_analysis.py:1-10` (add imports and constants)
- Modify: `tests/api/test_vspaero_analysis.py` (add test class)

- [ ] **Step 1: Write failing tests for `build_analysis_geoms`**

Add to `tests/api/test_vspaero_analysis.py` — new import and test class:

```python
# Add to imports at top of file:
from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult
from services.workers.cad_worker.openvsp_generator.vspaero_analysis import (
    AeroPoint,
    VspaeroReport,
    _compute_optimal_ld,
    _fit_cd0,
    _fit_cl_alpha,
    build_analysis_geoms,
    fake_vspaero_results,
)
```

Add helper and test class at the end of the file:

```python
def _mock_results(names: list[str]) -> list[GeometryBuildResult]:
    return [GeometryBuildResult(name=n, geom_id=f"id-{n}") for n in names]


class TestBuildAnalysisGeoms:
    def test_conventional_returns_main_wing_only(self):
        spec = _make_spec()
        results = _mock_results(["fuselage", "main_wing", "horizontal_tail", "vertical_tail"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing"]

    def test_twin_boom_returns_main_wing_only(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="twin_boom"))
        results = _mock_results(["fuselage", "main_wing", "horizontal_tail", "left_boom", "right_boom"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing"]

    def test_flying_wing_returns_main_wing_only(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="flying_wing"))
        results = _mock_results(["main_wing"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing"]

    def test_blended_wing_body_returns_main_wing_only(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="blended_wing_body"))
        results = _mock_results(["flat_body", "main_wing"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing"]

    def test_canard_returns_main_wing_and_canard(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="canard"))
        results = _mock_results(["fuselage", "main_wing", "canard", "horizontal_tail"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing", "id-canard"]

    def test_three_surface_returns_main_wing_and_canard(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="three_surface"))
        results = _mock_results(["fuselage", "main_wing", "canard", "horizontal_tail"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing", "id-canard"]

    def test_tandem_wing_returns_main_wing_and_rear_wing(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="tandem_wing"))
        results = _mock_results(["fuselage", "main_wing", "rear_wing"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing", "id-rear_wing"]

    def test_joined_wing_returns_main_wing_and_rear_wing(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="joined_wing"))
        results = _mock_results(["fuselage", "main_wing", "rear_wing"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing", "id-rear_wing"]

    def test_biplane_returns_main_wing_and_lower_wing(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="biplane"))
        results = _mock_results(["fuselage", "main_wing", "lower_wing", "horizontal_tail"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing", "id-lower_wing"]

    def test_box_wing_returns_main_wing_and_box_lower_wing(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="box_wing"))
        results = _mock_results(["fuselage", "main_wing", "box_lower_wing", "left_endplate", "right_endplate", "horizontal_tail"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing", "id-box_lower_wing"]

    def test_multi_fuselage_returns_main_wing_only(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="multi_fuselage"))
        results = _mock_results(["left_fuselage", "right_fuselage", "main_wing", "horizontal_tail"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing"]

    def test_missing_component_skipped_gracefully(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="canard"))
        results = _mock_results(["fuselage", "main_wing"])  # no canard
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing"]

    def test_unknown_layout_returns_main_wing_only(self):
        spec = _make_spec()  # conventional
        results = _mock_results(["fuselage", "main_wing"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_vspaero_analysis.py::TestBuildAnalysisGeoms -v`
Expected: FAIL — `ImportError: cannot import name 'build_analysis_geoms'`

- [ ] **Step 3: Implement `build_analysis_geoms` and `LAYOUT_ANALYSIS_NAMES`**

Add to `services/workers/cad_worker/openvsp_generator/vspaero_analysis.py` — new imports after existing imports (after line 8):

```python
from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult
```

Add the constant and function after the `VspaeroReport` class (after line 63, before `_cruise_mach`):

```python
LAYOUT_ANALYSIS_NAMES: dict[str, list[str]] = {
    "conventional": [],
    "twin_boom": [],
    "flying_wing": [],
    "blended_wing_body": [],
    "canard": ["canard"],
    "three_surface": ["canard"],
    "tandem_wing": ["rear_wing"],
    "joined_wing": ["rear_wing"],
    "biplane": ["lower_wing"],
    "box_wing": ["box_lower_wing"],
    "multi_fuselage": [],
}


def build_analysis_geoms(
    spec: AircraftSpec,
    build_results: list[GeometryBuildResult],
) -> list[str]:
    """Return geom IDs to include in VSPAERO analysis based on layout."""
    layout = spec.aircraft.layout.lower()
    extra_names = LAYOUT_ANALYSIS_NAMES.get(layout, [])
    components = {r.name: r.geom_id for r in build_results}
    geom_ids: list[str] = []
    if "main_wing" in components:
        geom_ids.append(components["main_wing"])
    for name in extra_names:
        if name in components:
            geom_ids.append(components[name])
    return geom_ids
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_vspaero_analysis.py::TestBuildAnalysisGeoms -v`
Expected: 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/workers/cad_worker/openvsp_generator/vspaero_analysis.py tests/api/test_vspaero_analysis.py
git commit -m "feat(vspaero): add build_analysis_geoms for layout-aware multi-surface analysis"
```

---

### Task 2: `VspaeroReport.components_analyzed` + `run_vspaero_analysis` signature change

**Files:**
- Modify: `services/workers/cad_worker/openvsp_generator/vspaero_analysis.py:32-63` (VspaeroReport)
- Modify: `services/workers/cad_worker/openvsp_generator/vspaero_analysis.py:135-148` (run_vspaero_analysis signature)
- Modify: `tests/api/test_vspaero_analysis.py` (update existing test, add new tests)

- [ ] **Step 1: Write failing test for `VspaeroReport.components_analyzed`**

Add to `tests/api/test_vspaero_analysis.py` in the `TestVspaeroReport` class:

```python
    def test_to_dict_includes_components_analyzed(self):
        sweep = [AeroPoint(alpha=0, cl=0.1, cd=0.025, cm=0.0, mach=0.0, beta=0.0)]
        report = VspaeroReport(
            status="success",
            method="VSPAERO_panel",
            alpha_sweep=sweep,
            optimal_ld=20.0,
            optimal_cl=0.5,
            optimal_alpha=3.0,
            components_analyzed=["main_wing", "canard"],
        )
        d = report.to_dict()
        assert d["components_analyzed"] == ["main_wing", "canard"]

    def test_to_dict_omits_empty_components_analyzed(self):
        report = VspaeroReport(status="success", method="VSPAERO_panel")
        d = report.to_dict()
        assert "components_analyzed" not in d
```

- [ ] **Step 2: Run test to verify it fails**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_vspaero_analysis.py::TestVspaeroReport::test_to_dict_includes_components_analyzed -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'components_analyzed'`

- [ ] **Step 3: Add `components_analyzed` field to `VspaeroReport`**

In `services/workers/cad_worker/openvsp_generator/vspaero_analysis.py`, modify the `VspaeroReport` dataclass.

Add after `span_load` field (line 42):
```python
    components_analyzed: list[str] = field(default_factory=list)
```

Update `to_dict()` method — add before the `error_message` check (around line 60):
```python
        if self.components_analyzed:
            d["components_analyzed"] = self.components_analyzed
```

The full `to_dict()` method becomes:
```python
    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "method": self.method,
            "optimal_ld": self.optimal_ld,
            "optimal_cl": self.optimal_cl,
            "optimal_alpha": self.optimal_alpha,
            "alpha_sweep": [p.to_dict() for p in self.alpha_sweep],
            "span_load": self.span_load,
        }
        if self.cruise_point is not None:
            d["cruise_point"] = self.cruise_point.to_dict()
        if self.cl_alpha is not None:
            d["cl_alpha"] = self.cl_alpha
        if self.cd0_estimate is not None:
            d["cd0_estimate"] = self.cd0_estimate
        if self.components_analyzed:
            d["components_analyzed"] = self.components_analyzed
        if self.error_message is not None:
            d["error_message"] = self.error_message
        return d
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_vspaero_analysis.py::TestVspaeroReport -v`
Expected: 4 tests PASS

- [ ] **Step 5: Write failing test for modified `run_vspaero_analysis` with multi-geom**

Add to `tests/api/test_vspaero_analysis.py`:

```python
class TestRunVspaeroMultiGeom:
    def test_accepts_list_of_geom_ids(self):
        """run_vspaero_analysis should accept geom_ids: list[str]."""
        class StubAdapter:
            def set_vspaero_ref_wing(self, wing_id):
                self._ref_wing = wing_id

            def write_vsp_file(self, path):
                pass

            def set_analysis_input_defaults(self, name):
                pass

            def set_int_analysis_input(self, name, key, vals, index=0):
                pass

            def set_double_analysis_input(self, name, key, vals):
                pass

            def exec_analysis(self, name):
                raise RuntimeError("VSPAERO not installed")

            def default_set_id(self):
                return 0

            def find_latest_results_id(self, name):
                return ""

            def create_set(self, name):
                return 1

            def add_to_set(self, set_id, geom_id):
                pass

        from services.workers.cad_worker.openvsp_generator.vspaero_analysis import (
            run_vspaero_analysis,
        )

        spec = _make_spec()
        adapter = StubAdapter()
        with pytest.raises(RuntimeError, match="VSPAERO not installed"):
            run_vspaero_analysis(adapter, spec, ["wing-1", "canard-1"])
        # Verify ref wing was set to first geom_id
        assert adapter._ref_wing == "wing-1"
```

- [ ] **Step 6: Run test to verify it fails**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_vspaero_analysis.py::TestRunVspaeroMultiGeom -v`
Expected: FAIL — `TypeError` on `run_vspaero_analysis()` (wrong signature)

- [ ] **Step 7: Modify `run_vspaero_analysis` signature and body**

In `services/workers/cad_worker/openvsp_generator/vspaero_analysis.py`, change the function signature and body.

Change the signature from:
```python
def run_vspaero_analysis(
    adapter: OpenVspAdapter,
    spec: AircraftSpec,
    wing_geom_id: str,
    *,
```
to:
```python
def run_vspaero_analysis(
    adapter: OpenVspAdapter,
    spec: AircraftSpec,
    geom_ids: list[str],
    *,
```

Change line `adapter.set_vspaero_ref_wing(wing_geom_id)` to:
```python
    adapter.set_vspaero_ref_wing(geom_ids[0])
```

Change the Set creation block from:
```python
        wing_set_id = adapter.create_set("Set_0")
        adapter.add_to_set(wing_set_id, wing_geom_id)
```
to:
```python
        analysis_set_id = adapter.create_set("Set_0")
        for gid in geom_ids:
            adapter.add_to_set(analysis_set_id, gid)
```

Update all references from `wing_set_id` to `analysis_set_id` in the rest of the function (3 occurrences: `set_int_analysis_input` calls for GeomSet in both `geom_analysis` and `sweep_analysis`).

The full updated function:

```python
def run_vspaero_analysis(
    adapter: OpenVspAdapter,
    spec: AircraftSpec,
    geom_ids: list[str],
    *,
    alpha_range: tuple[float, float] = (-4.0, 12.0),
    alpha_step: float = 1.0,
    mach: float | None = None,
    output_dir: "Path | None" = None,
) -> VspaeroReport:
    import os
    from pathlib import Path

    adapter.set_vspaero_ref_wing(geom_ids[0])

    if output_dir is not None:
        work_dir = str(output_dir)
        vsp_prefix = "aircraft"
    else:
        import tempfile
        work_dir = tempfile.mkdtemp(prefix="vspaero_")
        adapter.write_vsp_file(os.path.join(work_dir, "model.vsp3"))
        vsp_prefix = "model"

    orig_dir = os.getcwd()
    os.chdir(work_dir)
    try:
        analysis_set_id = adapter.create_set("Set_0")
        for gid in geom_ids:
            adapter.add_to_set(analysis_set_id, gid)

        geom_analysis = "VSPAEROComputeGeometry"
        adapter.set_analysis_input_defaults(geom_analysis)
        adapter.set_int_analysis_input(geom_analysis, "GeomSet", [analysis_set_id])
        adapter.set_int_analysis_input(geom_analysis, "ThinGeomSet", [0])
        adapter.set_int_analysis_input(geom_analysis, "Symmetry", [1])
        adapter.exec_analysis(geom_analysis)

        if not os.path.exists(f"{vsp_prefix}.vspgeom"):
            return VspaeroReport(status="failed", method="VSPAERO_panel", error_message="vspgeom generation failed")

        sweep_analysis = "VSPAEROSweep"
        adapter.set_analysis_input_defaults(sweep_analysis)
        adapter.set_int_analysis_input(sweep_analysis, "GeomSet", [analysis_set_id])
        adapter.set_int_analysis_input(sweep_analysis, "ThinGeomSet", [0])
        adapter.set_int_analysis_input(sweep_analysis, "Symmetry", [1])

        num_alphas = int(round((alpha_range[1] - alpha_range[0]) / alpha_step)) + 1
        adapter.set_double_analysis_input(sweep_analysis, "AlphaStart", [alpha_range[0]])
        adapter.set_double_analysis_input(sweep_analysis, "AlphaEnd", [alpha_range[1]])
        adapter.set_int_analysis_input(sweep_analysis, "AlphaNpts", [num_alphas])

        mach_val = mach if mach is not None else _cruise_mach(spec)
        adapter.set_double_analysis_input(sweep_analysis, "MachStart", [mach_val])
        adapter.set_double_analysis_input(sweep_analysis, "MachEnd", [mach_val])
        adapter.set_int_analysis_input(sweep_analysis, "MachNpts", [1])

        adapter.set_double_analysis_input(sweep_analysis, "BetaStart", [0.0])
        adapter.set_double_analysis_input(sweep_analysis, "BetaEnd", [0.0])
        adapter.set_int_analysis_input(sweep_analysis, "BetaNpts", [1])

        adapter.set_int_analysis_input(sweep_analysis, "WakeNumIter", [3])
        adapter.set_int_analysis_input(sweep_analysis, "NCPU", [1])

        adapter.exec_analysis(sweep_analysis)

        polar_id = adapter.find_latest_results_id("VSPAERO_Polar")
        if not polar_id:
            polar_id = adapter.find_latest_results_id("VSPAERO_History")
        if not polar_id:
            import logging
            vsp = adapter._module.vsp
            all_names = list(vsp.GetAllResultsNames())
            logging.getLogger(__name__).warning("VSPAERO_Polar not found. Available: %s", all_names)
            return VspaeroReport(status="failed", method="VSPAERO_panel", error_message="no polar results")

        cl_arr = adapter.get_double_results(polar_id, "CLtot")
        cd_arr = adapter.get_double_results(polar_id, "CDtot")
        cm_arr = adapter.get_double_results(polar_id, "CMytot")
    finally:
        os.chdir(orig_dir)
        if output_dir is None:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)

    alphas = []
    a = alpha_range[0]
    while a <= alpha_range[1] + 1e-6:
        alphas.append(round(a, 2))
        a += alpha_step

    sweep: list[AeroPoint] = []
    count = min(len(alphas), len(cl_arr), len(cd_arr), len(cm_arr))
    for i in range(count):
        sweep.append(AeroPoint(
            alpha=alphas[i] if i < len(alphas) else 0.0,
            cl=cl_arr[i], cd=cd_arr[i], cm=cm_arr[i],
            mach=mach_val, beta=0.0,
        ))

    if not sweep:
        return VspaeroReport(status="failed", method="VSPAERO_panel", error_message="no results")

    optimal_ld, optimal_cl, optimal_alpha = _compute_optimal_ld(sweep)
    cl_alpha = _fit_cl_alpha(sweep)
    cd0_estimate = _fit_cd0(sweep)

    cruise_point: AeroPoint | None = None
    cruise_cl = 0.5
    closest = min(sweep, key=lambda p: abs(p.cl - cruise_cl))
    cruise_point = closest

    return VspaeroReport(
        status="success",
        method="VSPAERO_panel",
        alpha_sweep=sweep,
        cruise_point=cruise_point,
        optimal_ld=round(optimal_ld, 3),
        optimal_cl=round(optimal_cl, 4),
        optimal_alpha=round(optimal_alpha, 2),
        cl_alpha=round(cl_alpha, 4) if cl_alpha is not None else None,
        cd0_estimate=cd0_estimate,
    )
```

- [ ] **Step 8: Update existing `TestRunVspaeroHandlesError` to use new signature**

In `tests/api/test_vspaero_analysis.py`, change the `test_adapter_failure` method call from:

```python
        run_vspaero_analysis(FailAdapter(), spec, "wing-1")
```
to:
```python
        run_vspaero_analysis(FailAdapter(), spec, ["wing-1"])
```

- [ ] **Step 9: Run all VSPAERO tests**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_vspaero_analysis.py -v`
Expected: All tests PASS

- [ ] **Step 10: Commit**

```bash
git add services/workers/cad_worker/openvsp_generator/vspaero_analysis.py tests/api/test_vspaero_analysis.py
git commit -m "feat(vspaero): multi-surface analysis with components_analyzed report field"
```

---

### Task 3: Update `backend.py` caller to use `build_analysis_geoms`

**Files:**
- Modify: `services/workers/cad_worker/openvsp_generator/backend.py:174-188` (VSPAERO caller block)

- [ ] **Step 1: Update the VSPAERO caller in `OpenVspBackend.generate`**

In `services/workers/cad_worker/openvsp_generator/backend.py`, change the import and VSPAERO caller block.

Add import (after existing vspaero_analysis import on line 177):
```python
            from services.workers.cad_worker.openvsp_generator.vspaero_analysis import (
                build_analysis_geoms,
                LAYOUT_ANALYSIS_NAMES,
                run_vspaero_analysis,
            )
```

Replace the VSPAERO caller block (lines 174-188) from:
```python
        vspaero_data: dict[str, Any] = {}
        if _vspaero_enabled():
            from services.workers.cad_worker.openvsp_generator.vspaero_analysis import (
                run_vspaero_analysis,
            )
            components = _components(build_results)
            wing_id = components.get("main_wing", "")
            if wing_id:
                try:
                    report = run_vspaero_analysis(
                        adapter, spec, wing_id, output_dir=output_dir,
                    )
                    vspaero_data = report.to_dict()
                except Exception as exc:
                    vspaero_data = {"status": "failed", "error_message": str(exc)}
```
to:
```python
        vspaero_data: dict[str, Any] = {}
        if _vspaero_enabled():
            from services.workers.cad_worker.openvsp_generator.vspaero_analysis import (
                build_analysis_geoms,
                LAYOUT_ANALYSIS_NAMES,
                run_vspaero_analysis,
            )
            geom_ids = build_analysis_geoms(spec, build_results)
            if geom_ids:
                try:
                    report = run_vspaero_analysis(
                        adapter, spec, geom_ids, output_dir=output_dir,
                    )
                    layout = spec.aircraft.layout.lower()
                    all_names = ["main_wing"] + LAYOUT_ANALYSIS_NAMES.get(layout, [])
                    component_map = _components(build_results)
                    report.components_analyzed = [
                        n for n in all_names if n in component_map
                    ]
                    vspaero_data = report.to_dict()
                except Exception as exc:
                    vspaero_data = {"status": "failed", "error_message": str(exc)}
```

- [ ] **Step 2: Run all tests**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/ -v -q`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add services/workers/cad_worker/openvsp_generator/backend.py
git commit -m "feat(vspaero): backend uses build_analysis_geoms for multi-surface analysis"
```

---

## Batch 2: Deep Design Layout-Aware Strategies

### Task 4: `LAYOUT_STRATEGIES` dictionary + unit tests

**Files:**
- Modify: `services/api/app/graph/deep_design_graph.py:30-38` (replace DEFAULT_STRATEGIES area with full dict)
- Modify: `tests/api/test_layout_builders.py` (add test classes)

- [ ] **Step 1: Write failing tests for layout strategies**

Add to `tests/api/test_layout_builders.py` — new imports and test classes:

```python
import json

import yaml
from pathlib import Path

from services.api.app.graph.deep_design_graph import (
    LAYOUT_STRATEGIES,
    DEFAULT_STRATEGIES,
    prepare_variants,
)


_EXAMPLE_SPEC_PATH = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


def _load_spec_dict() -> dict:
    with open(_EXAMPLE_SPEC_PATH) as f:
        return yaml.safe_load(f)


class TestLayoutStrategies:
    def test_canard_compact_varies_canard_span(self):
        strategies = LAYOUT_STRATEGIES["canard"]
        compact = strategies[0]
        assert compact["label"] == "compact"
        changes = compact["changes"]
        paths = {c["path"] for c in changes}
        assert "wing.span.value" in paths
        assert "canard.span.value" in paths
        canard_change = next(c for c in changes if c["path"] == "canard.span.value")
        assert canard_change["value"] == -0.5
        assert canard_change["op"] == "relative"

    def test_canard_extended_varies_canard_span(self):
        strategies = LAYOUT_STRATEGIES["canard"]
        extended = strategies[2]
        assert extended["label"] == "extended"
        canard_change = next(c for c in extended["changes"] if c["path"] == "canard.span.value")
        assert canard_change["value"] == 0.5

    def test_biplane_extended_varies_gap(self):
        strategies = LAYOUT_STRATEGIES["biplane"]
        extended = strategies[2]
        assert extended["label"] == "extended"
        gap_change = next(c for c in extended["changes"] if c["path"] == "second_wing.gap.value")
        assert gap_change["value"] == 0.2

    def test_biplane_compact_varies_gap(self):
        strategies = LAYOUT_STRATEGIES["biplane"]
        compact = strategies[0]
        gap_change = next(c for c in compact["changes"] if c["path"] == "second_wing.gap.value")
        assert gap_change["value"] == -0.2

    def test_tandem_wing_varies_rear_wing_span(self):
        strategies = LAYOUT_STRATEGIES["tandem_wing"]
        compact = strategies[0]
        assert compact["label"] == "compact"
        paths = {c["path"] for c in compact["changes"]}
        assert "wing.span.value" in paths
        assert "rear_wing.span.value" in paths
        rear_change = next(c for c in compact["changes"] if c["path"] == "rear_wing.span.value")
        assert rear_change["value"] == -1

    def test_box_wing_varies_gap(self):
        strategies = LAYOUT_STRATEGIES["box_wing"]
        extended = strategies[2]
        gap_change = next(c for c in extended["changes"] if c["path"] == "box_wing_config.gap.value")
        assert gap_change["value"] == 0.3

    def test_three_surface_same_as_canard(self):
        canard_paths = {(c["path"], c["value"]) for s in LAYOUT_STRATEGIES["canard"] for c in s["changes"]}
        three_paths = {(c["path"], c["value"]) for s in LAYOUT_STRATEGIES["three_surface"] for c in s["changes"]}
        assert canard_paths == three_paths

    def test_joined_wing_same_as_tandem(self):
        tandem_paths = {(c["path"], c["value"]) for s in LAYOUT_STRATEGIES["tandem_wing"] for c in s["changes"]}
        joined_paths = {(c["path"], c["value"]) for s in LAYOUT_STRATEGIES["joined_wing"] for c in s["changes"]}
        assert tandem_paths == joined_paths

    def test_conventional_uses_default_strategies(self):
        assert LAYOUT_STRATEGIES["conventional"] is DEFAULT_STRATEGIES

    def test_single_surface_layouts_use_default(self):
        for layout in ("twin_boom", "flying_wing", "blended_wing_body", "multi_fuselage"):
            assert LAYOUT_STRATEGIES[layout] is DEFAULT_STRATEGIES, f"{layout} should use DEFAULT_STRATEGIES"

    def test_unknown_layout_falls_back(self):
        strategies = LAYOUT_STRATEGIES.get("hypothetical_layout", LAYOUT_STRATEGIES["conventional"])
        assert strategies is DEFAULT_STRATEGIES

    def test_all_layouts_have_three_strategies(self):
        for layout, strategies in LAYOUT_STRATEGIES.items():
            labels = [s["label"] for s in strategies]
            assert labels == ["compact", "standard", "extended"], f"{layout} strategy labels incorrect"


class TestLayoutAwarePrepareVariants:
    def test_canard_compact_patches_canard_span(self):
        spec_dict = _load_spec_dict()
        spec_dict["aircraft"]["layout"] = "canard"
        spec_dict["canard"] = {
            "span": {"value": 3.0, "unit": "m", "source": "user"},
            "chord": {"value": 0.5, "unit": "m", "source": "user"},
        }
        state = {"base_spec": spec_dict, "constraints": {"variant_count": 3}}
        result = prepare_variants(state)
        compact = result["variants"][0]
        assert compact["label"] == "compact"
        patched = compact["patched_spec"]
        assert patched["wing"]["span"]["value"] < spec_dict["wing"]["span"]["value"]
        assert patched["canard"]["span"]["value"] < spec_dict["canard"]["span"]["value"]

    def test_biplane_extended_patches_gap(self):
        spec_dict = _load_spec_dict()
        spec_dict["aircraft"]["layout"] = "biplane"
        spec_dict["second_wing"] = {
            "span": {"value": 5.0, "unit": "m", "source": "user"},
            "chord": {"value": 0.8, "unit": "m", "source": "user"},
            "gap": {"value": 1.2, "unit": "m", "source": "user"},
        }
        state = {"base_spec": spec_dict, "constraints": {"variant_count": 3}}
        result = prepare_variants(state)
        extended = result["variants"][2]
        assert extended["label"] == "extended"
        patched = extended["patched_spec"]
        assert patched["second_wing"]["gap"]["value"] > spec_dict["second_wing"]["gap"]["value"]

    def test_conventional_unchanged(self):
        spec_dict = _load_spec_dict()
        state = {"base_spec": spec_dict, "constraints": {"variant_count": 3}}
        result = prepare_variants(state)
        assert len(result["variants"]) == 3
        assert result["variants"][0]["label"] == "compact"
        # Conventional compact only varies wing.span
        compact = result["variants"][0]
        patched = compact["patched_spec"]
        assert patched["wing"]["span"]["value"] < spec_dict["wing"]["span"]["value"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_layout_builders.py::TestLayoutStrategies -v`
Expected: FAIL — `ImportError: cannot import name 'LAYOUT_STRATEGIES'`

- [ ] **Step 3: Implement `LAYOUT_STRATEGIES` in `deep_design_graph.py`**

In `services/api/app/graph/deep_design_graph.py`, add after `DEFAULT_STRATEGIES` (after line 38):

```python
LAYOUT_STRATEGIES: dict[str, list[dict]] = {
    "conventional": DEFAULT_STRATEGIES,
    "canard": [
        {"label": "compact", "changes": [
            {"path": "wing.span.value", "value": -2, "op": "relative"},
            {"path": "canard.span.value", "value": -0.5, "op": "relative"},
        ]},
        {"label": "standard", "changes": []},
        {"label": "extended", "changes": [
            {"path": "wing.span.value", "value": 2, "op": "relative"},
            {"path": "canard.span.value", "value": 0.5, "op": "relative"},
        ]},
    ],
    "three_surface": [
        {"label": "compact", "changes": [
            {"path": "wing.span.value", "value": -2, "op": "relative"},
            {"path": "canard.span.value", "value": -0.5, "op": "relative"},
        ]},
        {"label": "standard", "changes": []},
        {"label": "extended", "changes": [
            {"path": "wing.span.value", "value": 2, "op": "relative"},
            {"path": "canard.span.value", "value": 0.5, "op": "relative"},
        ]},
    ],
    "tandem_wing": [
        {"label": "compact", "changes": [
            {"path": "wing.span.value", "value": -2, "op": "relative"},
            {"path": "rear_wing.span.value", "value": -1, "op": "relative"},
        ]},
        {"label": "standard", "changes": []},
        {"label": "extended", "changes": [
            {"path": "wing.span.value", "value": 2, "op": "relative"},
            {"path": "rear_wing.span.value", "value": 1, "op": "relative"},
        ]},
    ],
    "joined_wing": [
        {"label": "compact", "changes": [
            {"path": "wing.span.value", "value": -2, "op": "relative"},
            {"path": "rear_wing.span.value", "value": -1, "op": "relative"},
        ]},
        {"label": "standard", "changes": []},
        {"label": "extended", "changes": [
            {"path": "wing.span.value", "value": 2, "op": "relative"},
            {"path": "rear_wing.span.value", "value": 1, "op": "relative"},
        ]},
    ],
    "biplane": [
        {"label": "compact", "changes": [
            {"path": "wing.span.value", "value": -2, "op": "relative"},
            {"path": "second_wing.gap.value", "value": -0.2, "op": "relative"},
        ]},
        {"label": "standard", "changes": []},
        {"label": "extended", "changes": [
            {"path": "wing.span.value", "value": 2, "op": "relative"},
            {"path": "second_wing.gap.value", "value": 0.2, "op": "relative"},
        ]},
    ],
    "box_wing": [
        {"label": "compact", "changes": [
            {"path": "wing.span.value", "value": -2, "op": "relative"},
            {"path": "box_wing_config.gap.value", "value": -0.3, "op": "relative"},
        ]},
        {"label": "standard", "changes": []},
        {"label": "extended", "changes": [
            {"path": "wing.span.value", "value": 2, "op": "relative"},
            {"path": "box_wing_config.gap.value", "value": 0.3, "op": "relative"},
        ]},
    ],
    "twin_boom": DEFAULT_STRATEGIES,
    "flying_wing": DEFAULT_STRATEGIES,
    "blended_wing_body": DEFAULT_STRATEGIES,
    "multi_fuselage": DEFAULT_STRATEGIES,
}
```

- [ ] **Step 4: Run strategy tests to verify they pass**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_layout_builders.py::TestLayoutStrategies -v`
Expected: 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/api/app/graph/deep_design_graph.py tests/api/test_layout_builders.py
git commit -m "feat(deep-design): add LAYOUT_STRATEGIES for layout-aware variant generation"
```

---

### Task 5: Modify `prepare_variants` and `refine_variants` for layout-aware strategies

**Files:**
- Modify: `services/api/app/graph/deep_design_graph.py:101-137` (prepare_variants)
- Modify: `services/api/app/graph/deep_design_graph.py:244-256` (refine_variants)

- [ ] **Step 1: Run prepare_variants tests to verify they fail**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_layout_builders.py::TestLayoutAwarePrepareVariants -v`
Expected: FAIL — canard test fails because `prepare_variants` still uses `DEFAULT_STRATEGIES`

- [ ] **Step 2: Modify `prepare_variants` to use layout-aware strategies**

In `services/api/app/graph/deep_design_graph.py`, modify the `prepare_variants` function.

Change line:
```python
    strategies = DEFAULT_STRATEGIES[:variant_count]
```
to:
```python
    layout = base_spec.get("aircraft", {}).get("layout", "conventional") if isinstance(base_spec, dict) else "conventional"
    layout_strategies = LAYOUT_STRATEGIES.get(layout, LAYOUT_STRATEGIES["conventional"])
    strategies = layout_strategies[:variant_count]
```

The full updated `prepare_variants` function:

```python
@observe_node("prepare_variants")
def prepare_variants(state: DeepDesignState) -> dict:
    """Build variant specs from base spec and layout-aware strategies."""
    base_spec = state.get("base_spec")
    constraints = state.get("constraints", {})
    variant_count = constraints.get("variant_count", 3)

    if not base_spec:
        return {
            "status": "failed",
            "error_message": "no base_spec provided for exploration",
        }

    layout = base_spec.get("aircraft", {}).get("layout", "conventional") if isinstance(base_spec, dict) else "conventional"
    layout_strategies = LAYOUT_STRATEGIES.get(layout, LAYOUT_STRATEGIES["conventional"])
    strategies = layout_strategies[:variant_count]
    while len(strategies) < variant_count:
        strategies.append({
            "label": f"variant_{len(strategies) + 1}",
            "changes": [],
        })

    variants = []
    for strategy in strategies:
        changes = strategy.get("changes", [])
        if any(c.get("op") == "relative" for c in changes):
            patched = json.loads(json.dumps(base_spec))
            for change in changes:
                if change.get("op") == "relative":
                    _apply_relative(patched, change["path"], change["value"])
                else:
                    _set_nested(patched, change["path"], change["value"])
            variants.append({"label": strategy["label"], "changes": [
                {"path": c["path"], "value": c["value"]}
                for c in changes if c.get("op") != "relative"
            ], "patched_spec": patched})
        else:
            variants.append({"label": strategy["label"], "changes": changes})

    return {"variants": variants, "status": "running"}
```

- [ ] **Step 3: Run prepare_variants tests**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_layout_builders.py::TestLayoutAwarePrepareVariants -v`
Expected: 3 tests PASS

- [ ] **Step 4: Modify `refine_variants` to use layout-aware strategies**

In `services/api/app/graph/deep_design_graph.py`, in the `refine_variants` function, change the strategy lookup.

Change from:
```python
    for strategy in DEFAULT_STRATEGIES[:variant_count]:
```
to:
```python
    layout = base_spec.get("aircraft", {}).get("layout", "conventional") if isinstance(base_spec, dict) else "conventional"
    layout_strategies = LAYOUT_STRATEGIES.get(layout, LAYOUT_STRATEGIES["conventional"])
    for strategy in layout_strategies[:variant_count]:
```

The context around this change (lines 243-256):
```python
    # Increase delta by 50% for next iteration
    delta_multiplier = 1.5
    refined_strategies = []
    layout = base_spec.get("aircraft", {}).get("layout", "conventional") if isinstance(base_spec, dict) else "conventional"
    layout_strategies = LAYOUT_STRATEGIES.get(layout, LAYOUT_STRATEGIES["conventional"])
    for strategy in layout_strategies[:variant_count]:
        refined_changes = []
```

- [ ] **Step 5: Run all deep design tests**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_deep_design_graph.py tests/api/test_deep_design_api.py tests/api/test_layout_builders.py -v -q`
Expected: All tests PASS

- [ ] **Step 6: Run full test suite**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/ -q`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add services/api/app/graph/deep_design_graph.py
git commit -m "feat(deep-design): prepare_variants and refine_variants use layout-aware strategies"
```

---

## Batch 3: Documentation

### Task 6: Update layout maturity matrix

**Files:**
- Modify: `docs/layout-maturity-matrix.md` (VSPAERO and Deep Design rows)

- [ ] **Step 1: Update the maturity matrix**

In `docs/layout-maturity-matrix.md`, change the VSPAERO row from `⚠️` to `✅` for all layouts, and update Deep Design row similarly.

In the maturity matrix table, change the VSPAERO row:
```
| **VSPAERO** | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ |
```
to:
```
| **VSPAERO** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
```

Change the Deep Design row:
```
| **Deep Design** | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ |
```
to:
```
| **Deep Design** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
```

Update the **VSPAERO Analysis** section — change heading and content:

```markdown
### VSPAERO Analysis — ✅ All layouts (multi-surface)

VSPAERO analysis runs on **all aerodynamic surfaces** based on layout:

| Layout | Surfaces analyzed |
|--------|------------------|
| conventional, twin_boom, flying_wing, blended_wing_body, multi_fuselage | main_wing only |
| canard, three_surface | main_wing + canard |
| tandem_wing, joined_wing | main_wing + rear_wing |
| biplane | main_wing + lower_wing |
| box_wing | main_wing + box_lower_wing |

Results reflect combined multi-surface aerodynamics. `VspaeroReport.components_analyzed` lists which surfaces were included.
```

Update the **Deep Design Compatibility** section:

```markdown
### Deep Design Compatibility — ✅ All layouts (layout-aware strategies)

The Deep Design pipeline varies layout-specific fields when generating variants:

| Layout | Fields varied |
|--------|--------------|
| conventional, twin_boom, flying_wing, blended_wing_body, multi_fuselage | wing.span ±2m |
| canard, three_surface | wing.span ±2m, canard.span ±0.5m |
| tandem_wing, joined_wing | wing.span ±2m, rear_wing.span ±1m |
| biplane | wing.span ±2m, second_wing.gap ±0.2m |
| box_wing | wing.span ±2m, box_wing_config.gap ±0.3m |
```

Remove the **Highest-risk layouts** section's VSPAERO/Deep Design entries, or mark them as resolved.

- [ ] **Step 2: Commit**

```bash
git add docs/layout-maturity-matrix.md
git commit -m "docs: update maturity matrix for VSPAERO multi-surface + Deep Design layout-aware"
```
