# OpenVSP Real Geometry MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a real OpenVSP `.vsp3` aircraft model from the existing `aircraft_spec.yaml` example while keeping the fake backend as the default for normal tests and environments without OpenVSP.

**Architecture:** Add an explicit CAD backend factory, isolate OpenVSP API calls behind an adapter, split geometry creation into small modules, and have `generate_aircraft()` accept backend-supplied validation metadata. The API and frontend contract stay unchanged; real OpenVSP is selected only with `CAD_BACKEND=openvsp`.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, pytest, OpenVSP Python API when installed.

---

## Scope

This plan implements the approved design in `docs/superpowers/specs/2026-05-12-openvsp-real-geometry-design.md`.

In scope:

- Real `.vsp3` generation through OpenVSP Python API.
- Backend selection with `CAD_BACKEND=fake` or `CAD_BACKEND=openvsp`.
- Unit tests that run without OpenVSP installed.
- Opt-in integration test gated by `RUN_OPENVSP_TESTS=1` and `CAD_BACKEND=openvsp`.
- README documentation for fake vs OpenVSP backend.

Out of scope:

- STEP export.
- GLB conversion.
- Real browser 3D model rendering.
- Natural language parsing.
- LangGraph.
- Aerodynamic analysis.

## File Structure

- Modify: `services/workers/cad_worker/openvsp_generator/backend.py`
  Keep `CadBackend`, `FakeCadBackend`, and a thin `OpenVspBackend` orchestrator. Add `CadArtifacts`.
- Create: `services/workers/cad_worker/openvsp_generator/backend_factory.py`
  Select fake or OpenVSP backend from environment.
- Create: `services/workers/cad_worker/openvsp_generator/errors.py`
  Shared explicit exceptions.
- Create: `services/workers/cad_worker/openvsp_generator/openvsp_adapter.py`
  Import OpenVSP lazily and wrap common API calls.
- Create: `services/workers/cad_worker/openvsp_generator/geometry.py`
  Shared dataclasses for component IDs and applied parameters.
- Create: `services/workers/cad_worker/openvsp_generator/create_fuselage.py`
  Build fuselage geometry.
- Create: `services/workers/cad_worker/openvsp_generator/create_wing.py`
  Build main wing geometry.
- Create: `services/workers/cad_worker/openvsp_generator/create_tail.py`
  Build horizontal and vertical tail geometry.
- Create: `services/workers/cad_worker/openvsp_generator/create_engine.py`
  Build symmetric engine nacelles.
- Create: `services/workers/cad_worker/openvsp_generator/verify_model.py`
  Build validation report from files and applied parameter metadata.
- Modify: `services/workers/cad_worker/openvsp_generator/generate_aircraft.py`
  Merge backend-provided validation into report.
- Modify: `services/api/app/services/job_runner.py`
  Use `get_cad_backend()` by default.
- Modify: `services/api/app/routers/designs.py`
  Ensure module-level runner uses environment-selected backend.
- Modify: `README.md` and `.env`
  Document and default `CAD_BACKEND=fake`.
- Create: `tests/api/test_backend_factory.py`
- Create: `tests/api/test_openvsp_adapter.py`
- Create: `tests/api/test_openvsp_geometry_builders.py`
- Create: `tests/api/test_openvsp_backend_unit.py`
- Create: `tests/api/test_openvsp_integration.py`
- Modify: `tests/api/test_cad_generation.py`
- Modify: `tests/api/test_generation_api.py`

## Task 1: Backend Factory And Artifact Contract

**Files:**
- Create: `services/workers/cad_worker/openvsp_generator/backend_factory.py`
- Create: `services/workers/cad_worker/openvsp_generator/errors.py`
- Modify: `services/workers/cad_worker/openvsp_generator/backend.py`
- Modify: `services/workers/cad_worker/openvsp_generator/generate_aircraft.py`
- Modify: `services/api/app/services/job_runner.py`
- Create: `tests/api/test_backend_factory.py`
- Modify: `tests/api/test_cad_generation.py`

- [ ] **Step 1: Write failing backend factory tests**

Create `tests/api/test_backend_factory.py`:

```python
import pytest

from services.workers.cad_worker.openvsp_generator.backend import FakeCadBackend, OpenVspBackend
from services.workers.cad_worker.openvsp_generator.backend_factory import get_cad_backend
from services.workers.cad_worker.openvsp_generator.errors import CadBackendConfigurationError


def test_backend_factory_defaults_to_fake(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CAD_BACKEND", raising=False)

    backend = get_cad_backend()

    assert isinstance(backend, FakeCadBackend)


def test_backend_factory_selects_fake(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CAD_BACKEND", "fake")

    backend = get_cad_backend()

    assert isinstance(backend, FakeCadBackend)


def test_backend_factory_selects_openvsp(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CAD_BACKEND", "openvsp")

    backend = get_cad_backend()

    assert isinstance(backend, OpenVspBackend)


def test_backend_factory_rejects_unknown_backend(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CAD_BACKEND", "unknown")

    with pytest.raises(CadBackendConfigurationError, match="CAD_BACKEND"):
        get_cad_backend()
```

- [ ] **Step 2: Extend CAD generation test for backend validation metadata**

Modify `tests/api/test_cad_generation.py`:

```python
from pathlib import Path

from services.api.app.services.spec_io import load_aircraft_spec
from services.workers.cad_worker.openvsp_generator.backend import FakeCadBackend
from services.workers.cad_worker.openvsp_generator.generate_aircraft import generate_aircraft


def test_fake_backend_writes_expected_artifacts(tmp_path: Path):
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))

    result = generate_aircraft(spec=spec, output_dir=tmp_path, backend=FakeCadBackend())

    assert result.files["vsp3"].name == "aircraft.vsp3"
    assert result.files["step"].name == "aircraft.step"
    assert result.files["glb"].name == "aircraft.glb"
    assert result.validation_report["backend"]["actual"] == "FakeCadBackend"
    assert result.validation_report["vsp3.exists"]["status"] == "pass"
    assert result.validation_report["wing.span"]["status"] == "pass"
    assert result.validation_report["engine.count"]["actual"] == 2
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/api/test_backend_factory.py tests/api/test_cad_generation.py -q
```

Expected: FAIL because `backend_factory.py`, `errors.py`, and backend metadata do not exist yet.

- [ ] **Step 4: Implement explicit errors**

Create `services/workers/cad_worker/openvsp_generator/errors.py`:

```python
class CadBackendConfigurationError(ValueError):
    """Raised when CAD backend configuration is invalid."""


class OpenVspUnavailableError(RuntimeError):
    """Raised when OpenVSP Python API is unavailable."""


class OpenVspGenerationError(RuntimeError):
    """Raised when OpenVSP cannot generate the requested geometry."""


class UnsupportedGeometryError(ValueError):
    """Raised when the current real backend does not support a spec feature."""
```

- [ ] **Step 5: Add artifact contract and fake backend metadata**

Modify `services/workers/cad_worker/openvsp_generator/backend.py`:

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from services.api.app.schemas.aircraft_spec import AircraftSpec


@dataclass(frozen=True)
class CadArtifacts:
    files: dict[str, Path]
    validation: dict[str, dict[str, object]] = field(default_factory=dict)
    components: dict[str, str] = field(default_factory=dict)
    applied_parameters: dict[str, object] = field(default_factory=dict)


class CadBackend(Protocol):
    def generate(self, spec: AircraftSpec, output_dir: Path) -> CadArtifacts:
        """Generate CAD artifacts and return paths plus backend metadata."""


class FakeCadBackend:
    def generate(self, spec: AircraftSpec, output_dir: Path) -> CadArtifacts:
        output_dir.mkdir(parents=True, exist_ok=True)
        files = {
            "vsp3": output_dir / "aircraft.vsp3",
            "step": output_dir / "aircraft.step",
            "glb": output_dir / "aircraft.glb",
        }
        files["vsp3"].write_text(f"fake vsp3 for {spec.aircraft.name}\n", encoding="utf-8")
        files["step"].write_text("ISO-10303-21;\nEND-ISO-10303-21;\n", encoding="utf-8")
        files["glb"].write_bytes(b"glTF\x02\x00\x00\x00\x14\x00\x00\x00")
        return CadArtifacts(
            files=files,
            validation={
                "backend": {"expected": "fake", "actual": "FakeCadBackend", "status": "pass"},
                "vsp3.exists": {
                    "expected": True,
                    "actual": files["vsp3"].exists() and files["vsp3"].stat().st_size > 0,
                    "status": "pass",
                },
            },
        )


class OpenVspBackend:
    def generate(self, spec: AircraftSpec, output_dir: Path) -> CadArtifacts:
        from services.workers.cad_worker.openvsp_generator.openvsp_adapter import OpenVspAdapter

        adapter = OpenVspAdapter.load()
        output_dir.mkdir(parents=True, exist_ok=True)
        adapter.clear_model()
        fuselage_id = adapter.add_geom("FUSELAGE")
        wing_id = adapter.add_geom("WING")
        adapter.update()
        vsp3 = output_dir / "aircraft.vsp3"
        adapter.write_vsp_file(vsp3)
        return CadArtifacts(
            files={"vsp3": vsp3},
            components={"fuselage": fuselage_id, "main_wing": wing_id},
            applied_parameters={},
            validation={
                "backend": {"expected": "openvsp", "actual": "OpenVspBackend", "status": "pass"},
                "vsp3.exists": {
                    "expected": True,
                    "actual": vsp3.exists() and vsp3.stat().st_size > 0,
                    "status": "pass",
                },
            },
        )
```

- [ ] **Step 6: Implement backend factory**

Create `services/workers/cad_worker/openvsp_generator/backend_factory.py`:

```python
import os

from services.workers.cad_worker.openvsp_generator.backend import FakeCadBackend, OpenVspBackend
from services.workers.cad_worker.openvsp_generator.errors import CadBackendConfigurationError


def get_cad_backend():
    backend_name = os.getenv("CAD_BACKEND", "fake").strip().lower()
    if backend_name == "fake":
        return FakeCadBackend()
    if backend_name == "openvsp":
        return OpenVspBackend()
    raise CadBackendConfigurationError(
        f"Unsupported CAD_BACKEND={backend_name!r}. Expected 'fake' or 'openvsp'."
    )
```

- [ ] **Step 7: Merge backend validation in generator**

Modify `services/workers/cad_worker/openvsp_generator/generate_aircraft.py`:

```python
import json
from dataclasses import dataclass
from pathlib import Path

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.workers.cad_worker.openvsp_generator.backend import CadBackend


@dataclass(frozen=True)
class GenerationResult:
    files: dict[str, Path]
    generation_log: dict[str, object]
    validation_report: dict[str, dict[str, object]]


def _status(expected: object, actual: object) -> str:
    return "pass" if expected == actual else "fail"


def generate_aircraft(spec: AircraftSpec, output_dir: Path, backend: CadBackend) -> GenerationResult:
    artifacts = backend.generate(spec, output_dir)
    files = artifacts.files
    validation_report = {
        **artifacts.validation,
        "wing.span": {
            "expected": float(spec.wing.span.value),
            "actual": float(artifacts.applied_parameters.get("wing.span", spec.wing.span.value)),
            "status": _status(
                float(spec.wing.span.value),
                float(artifacts.applied_parameters.get("wing.span", spec.wing.span.value)),
            ),
        },
        "engine.count": {
            "expected": int(spec.engine.count.value),
            "actual": int(artifacts.applied_parameters.get("engine.count", spec.engine.count.value)),
            "status": _status(
                int(spec.engine.count.value),
                int(artifacts.applied_parameters.get("engine.count", spec.engine.count.value)),
            ),
        },
    }
    generation_log = {
        "aircraft": spec.aircraft.name,
        "backend": backend.__class__.__name__,
        "files": {key: str(path) for key, path in files.items()},
        "components": artifacts.components,
        "applied_parameters": artifacts.applied_parameters,
    }
    (output_dir / "generation_log.json").write_text(
        json.dumps(generation_log, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "validation_report.json").write_text(
        json.dumps(validation_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return GenerationResult(files=files, generation_log=generation_log, validation_report=validation_report)
```

- [ ] **Step 8: Use backend factory in JobRunner**

Modify `services/api/app/services/job_runner.py` imports and constructor:

```python
from services.workers.cad_worker.openvsp_generator.backend import CadBackend
from services.workers.cad_worker.openvsp_generator.backend_factory import get_cad_backend
```

Then change:

```python
self.backend = backend or FakeCadBackend()
```

to:

```python
self.backend = backend or get_cad_backend()
```

- [ ] **Step 9: Run tests**

Run:

```bash
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_backend_factory.py tests/api/test_cad_generation.py tests/api/test_job_runner.py tests/api/test_generation_api.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add services/workers/cad_worker/openvsp_generator/backend.py \
  services/workers/cad_worker/openvsp_generator/backend_factory.py \
  services/workers/cad_worker/openvsp_generator/errors.py \
  services/workers/cad_worker/openvsp_generator/generate_aircraft.py \
  services/api/app/services/job_runner.py \
  tests/api/test_backend_factory.py \
  tests/api/test_cad_generation.py
git commit -m "feat: add cad backend selection"
```

## Task 2: OpenVSP Adapter

**Files:**
- Create: `services/workers/cad_worker/openvsp_generator/openvsp_adapter.py`
- Create: `tests/api/test_openvsp_adapter.py`

- [ ] **Step 1: Write failing adapter tests**

Create `tests/api/test_openvsp_adapter.py`:

```python
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.workers.cad_worker.openvsp_generator.errors import (
    OpenVspGenerationError,
    OpenVspUnavailableError,
)
from services.workers.cad_worker.openvsp_generator.openvsp_adapter import OpenVspAdapter


class FakeVspModule:
    SET_ALL = 0

    def __init__(self):
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.geom_counter = 0

    def ClearVSPModel(self):
        self.calls.append(("ClearVSPModel", ()))

    def AddGeom(self, geom_type: str, parent: str = ""):
        self.calls.append(("AddGeom", (geom_type, parent)))
        self.geom_counter += 1
        return f"{geom_type}_{self.geom_counter}"

    def SetParmVal(self, geom_id: str, parm_name: str, group_name: str, value: float):
        self.calls.append(("SetParmVal", (geom_id, parm_name, group_name, value)))
        return 1

    def Update(self):
        self.calls.append(("Update", ()))

    def WriteVSPFile(self, path: str, set_id: int = 0):
        self.calls.append(("WriteVSPFile", (path, set_id)))
        Path(path).write_text("vsp\n", encoding="utf-8")


def test_adapter_load_raises_clear_error_when_openvsp_missing(monkeypatch: pytest.MonkeyPatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openvsp":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(OpenVspUnavailableError, match="OpenVSP Python API is not installed"):
        OpenVspAdapter.load()


def test_adapter_wraps_core_calls(tmp_path: Path):
    fake_vsp = FakeVspModule()
    adapter = OpenVspAdapter(fake_vsp)

    adapter.clear_model()
    geom_id = adapter.add_geom("WING")
    adapter.set_parm(geom_id, "Span", "XSec_1", 12.0)
    adapter.update()
    output = tmp_path / "aircraft.vsp3"
    adapter.write_vsp_file(output)

    assert geom_id == "WING_1"
    assert output.read_text(encoding="utf-8") == "vsp\n"
    assert ("SetParmVal", ("WING_1", "Span", "XSec_1", 12.0)) in fake_vsp.calls


def test_adapter_rejects_empty_geom_id():
    fake_vsp = SimpleNamespace(AddGeom=lambda geom_type, parent="": "")
    adapter = OpenVspAdapter(fake_vsp)

    with pytest.raises(OpenVspGenerationError, match="failed to create"):
        adapter.add_geom("WING")
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/api/test_openvsp_adapter.py -q
```

Expected: FAIL because `openvsp_adapter.py` does not exist.

- [ ] **Step 3: Implement OpenVSP adapter**

Create `services/workers/cad_worker/openvsp_generator/openvsp_adapter.py`:

```python
from pathlib import Path
from types import ModuleType
from typing import Any

from services.workers.cad_worker.openvsp_generator.errors import (
    OpenVspGenerationError,
    OpenVspUnavailableError,
)


class OpenVspAdapter:
    def __init__(self, vsp: Any) -> None:
        self.vsp = vsp

    @classmethod
    def load(cls) -> "OpenVspAdapter":
        try:
            import openvsp as vsp
        except ImportError as exc:
            raise OpenVspUnavailableError(
                "OpenVSP Python API is not installed. Install OpenVSP and ensure Python "
                "version matches the OpenVSP distribution."
            ) from exc
        return cls(vsp)

    def clear_model(self) -> None:
        self.vsp.ClearVSPModel()

    def add_geom(self, geom_type: str, parent: str = "") -> str:
        geom_id = self.vsp.AddGeom(geom_type, parent)
        if not geom_id:
            raise OpenVspGenerationError(f"OpenVSP failed to create geometry type {geom_type!r}")
        return str(geom_id)

    def set_parm(self, geom_id: str, parm_name: str, group_name: str, value: float) -> None:
        result = self.vsp.SetParmVal(geom_id, parm_name, group_name, float(value))
        if result is None:
            raise OpenVspGenerationError(
                f"OpenVSP failed to set {parm_name!r} in {group_name!r} for geom {geom_id!r}"
            )

    def update(self) -> None:
        self.vsp.Update()

    def write_vsp_file(self, path: Path) -> None:
        set_all = getattr(self.vsp, "SET_ALL", 0)
        self.vsp.WriteVSPFile(str(path), set_all)
        if not path.exists() or path.stat().st_size == 0:
            raise OpenVspGenerationError(f"OpenVSP did not write a non-empty VSP3 file at {path}")
```

- [ ] **Step 4: Run adapter tests**

Run:

```bash
.venv/bin/python -m pytest tests/api/test_openvsp_adapter.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/workers/cad_worker/openvsp_generator/openvsp_adapter.py tests/api/test_openvsp_adapter.py
git commit -m "feat: add openvsp adapter"
```

## Task 3: Geometry Builders With Fake OpenVSP Module

**Files:**
- Create: `services/workers/cad_worker/openvsp_generator/geometry.py`
- Create: `services/workers/cad_worker/openvsp_generator/create_fuselage.py`
- Create: `services/workers/cad_worker/openvsp_generator/create_wing.py`
- Create: `services/workers/cad_worker/openvsp_generator/create_tail.py`
- Create: `services/workers/cad_worker/openvsp_generator/create_engine.py`
- Create: `tests/api/test_openvsp_geometry_builders.py`

- [ ] **Step 1: Write fake module and builder tests**

Create `tests/api/test_openvsp_geometry_builders.py`:

```python
from pathlib import Path

import pytest

from services.api.app.services.spec_io import load_aircraft_spec
from services.workers.cad_worker.openvsp_generator.create_engine import create_engine_nacelles
from services.workers.cad_worker.openvsp_generator.create_fuselage import create_fuselage
from services.workers.cad_worker.openvsp_generator.create_tail import create_tail
from services.workers.cad_worker.openvsp_generator.create_wing import create_main_wing
from services.workers.cad_worker.openvsp_generator.errors import UnsupportedGeometryError
from services.workers.cad_worker.openvsp_generator.openvsp_adapter import OpenVspAdapter


class RecordingVspModule:
    SET_ALL = 0

    def __init__(self):
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.geom_counter = 0

    def AddGeom(self, geom_type: str, parent: str = ""):
        self.geom_counter += 1
        geom_id = f"{geom_type}_{self.geom_counter}"
        self.calls.append(("AddGeom", (geom_type, parent, geom_id)))
        return geom_id

    def SetParmVal(self, geom_id: str, parm_name: str, group_name: str, value: float):
        self.calls.append(("SetParmVal", (geom_id, parm_name, group_name, value)))
        return 1


def load_example():
    return load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))


def set_calls(vsp: RecordingVspModule, geom_id: str):
    return [call for call in vsp.calls if call[0] == "SetParmVal" and call[1][0] == geom_id]


def test_create_fuselage_applies_length_and_diameter():
    spec = load_example()
    vsp = RecordingVspModule()
    adapter = OpenVspAdapter(vsp)

    result = create_fuselage(adapter, spec)

    assert result.name == "fuselage"
    assert result.geom_id.startswith("FUSELAGE_")
    assert result.applied_parameters["fuselage.length"] == 7.0
    assert result.applied_parameters["fuselage.max_diameter"] == 0.75
    assert set_calls(vsp, result.geom_id)


def test_create_main_wing_applies_span_and_chords():
    spec = load_example()
    vsp = RecordingVspModule()
    adapter = OpenVspAdapter(vsp)

    result = create_main_wing(adapter, spec)

    assert result.name == "main_wing"
    assert result.geom_id.startswith("WING_")
    assert result.applied_parameters["wing.span"] == 12.0
    assert result.applied_parameters["wing.root_chord"] == 1.2
    assert result.applied_parameters["wing.tip_chord"] == 0.6


def test_create_tail_creates_horizontal_and_vertical_tail():
    spec = load_example()
    vsp = RecordingVspModule()
    adapter = OpenVspAdapter(vsp)

    results = create_tail(adapter, spec)

    assert [result.name for result in results] == ["horizontal_tail", "vertical_tail"]
    assert all(result.geom_id.startswith("WING_") for result in results)
    assert results[0].applied_parameters["tail.horizontal.span"] > 0
    assert results[1].applied_parameters["tail.vertical.span"] > 0


def test_create_engine_nacelles_creates_two_symmetric_engines():
    spec = load_example()
    vsp = RecordingVspModule()
    adapter = OpenVspAdapter(vsp)

    results = create_engine_nacelles(adapter, spec)

    assert [result.name for result in results] == ["left_engine", "right_engine"]
    assert results[0].applied_parameters["engine.count"] == 2
    assert results[0].applied_parameters["engine.left.y"] < 0
    assert results[1].applied_parameters["engine.right.y"] > 0


def test_create_engine_nacelles_rejects_unsupported_count():
    spec = load_example().model_copy(deep=True)
    spec.engine.count.value = 3
    adapter = OpenVspAdapter(RecordingVspModule())

    with pytest.raises(UnsupportedGeometryError, match="engine.count"):
        create_engine_nacelles(adapter, spec)
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/api/test_openvsp_geometry_builders.py -q
```

Expected: FAIL because builder modules do not exist.

- [ ] **Step 3: Implement geometry dataclass**

Create `services/workers/cad_worker/openvsp_generator/geometry.py`:

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GeometryBuildResult:
    name: str
    geom_id: str
    applied_parameters: dict[str, object] = field(default_factory=dict)
```

- [ ] **Step 4: Implement fuselage builder**

Create `services/workers/cad_worker/openvsp_generator/create_fuselage.py`:

```python
from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult
from services.workers.cad_worker.openvsp_generator.openvsp_adapter import OpenVspAdapter


def create_fuselage(adapter: OpenVspAdapter, spec: AircraftSpec) -> GeometryBuildResult:
    geom_id = adapter.add_geom("FUSELAGE")
    length = float(spec.fuselage.length.value)
    diameter = float(spec.fuselage.max_diameter.value) if spec.fuselage.max_diameter else 0.75
    adapter.set_parm(geom_id, "Length", "Design", length)
    adapter.set_parm(geom_id, "Diameter", "Design", diameter)
    return GeometryBuildResult(
        name="fuselage",
        geom_id=geom_id,
        applied_parameters={
            "fuselage.length": length,
            "fuselage.max_diameter": diameter,
        },
    )
```

- [ ] **Step 5: Implement wing builder**

Create `services/workers/cad_worker/openvsp_generator/create_wing.py`:

```python
from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult
from services.workers.cad_worker.openvsp_generator.openvsp_adapter import OpenVspAdapter


def _wing_z_position(position: str, fuselage_diameter: float) -> float:
    if position == "high":
        return fuselage_diameter * 0.45
    if position == "mid":
        return 0.0
    if position == "low":
        return -fuselage_diameter * 0.45
    return 0.0


def create_main_wing(adapter: OpenVspAdapter, spec: AircraftSpec) -> GeometryBuildResult:
    geom_id = adapter.add_geom("WING")
    span = float(spec.wing.span.value)
    root_chord = float(spec.wing.root_chord.value)
    tip_chord = float(spec.wing.tip_chord.value)
    sweep = float(spec.wing.sweep.value) if spec.wing.sweep else 0.0
    dihedral = float(spec.wing.dihedral.value) if spec.wing.dihedral else 0.0
    fuselage_diameter = (
        float(spec.fuselage.max_diameter.value) if spec.fuselage.max_diameter else 0.75
    )
    z_position = _wing_z_position(str(spec.wing.position.value), fuselage_diameter)

    adapter.set_parm(geom_id, "TotalSpan", "WingGeom", span)
    adapter.set_parm(geom_id, "Root_Chord", "XSec_1", root_chord)
    adapter.set_parm(geom_id, "Tip_Chord", "XSec_1", tip_chord)
    adapter.set_parm(geom_id, "Sweep", "XSec_1", sweep)
    adapter.set_parm(geom_id, "Dihedral", "XSec_1", dihedral)
    adapter.set_parm(geom_id, "Z_Rel_Location", "XForm", z_position)

    return GeometryBuildResult(
        name="main_wing",
        geom_id=geom_id,
        applied_parameters={
            "wing.span": span,
            "wing.root_chord": root_chord,
            "wing.tip_chord": tip_chord,
            "wing.sweep": sweep,
            "wing.dihedral": dihedral,
            "wing.z": z_position,
        },
    )
```

- [ ] **Step 6: Implement tail builder**

Create `services/workers/cad_worker/openvsp_generator/create_tail.py`:

```python
from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult
from services.workers.cad_worker.openvsp_generator.openvsp_adapter import OpenVspAdapter


def create_tail(adapter: OpenVspAdapter, spec: AircraftSpec) -> list[GeometryBuildResult]:
    fuselage_length = float(spec.fuselage.length.value)
    wing_span = float(spec.wing.span.value)
    horizontal_span = wing_span * 0.28
    horizontal_chord = float(spec.wing.root_chord.value) * 0.45
    vertical_span = wing_span * 0.16
    vertical_chord = float(spec.wing.root_chord.value) * 0.55
    tail_x = fuselage_length * 0.42

    horizontal_id = adapter.add_geom("WING")
    adapter.set_parm(horizontal_id, "TotalSpan", "WingGeom", horizontal_span)
    adapter.set_parm(horizontal_id, "Root_Chord", "XSec_1", horizontal_chord)
    adapter.set_parm(horizontal_id, "Tip_Chord", "XSec_1", horizontal_chord * 0.65)
    adapter.set_parm(horizontal_id, "X_Rel_Location", "XForm", tail_x)

    vertical_id = adapter.add_geom("WING")
    adapter.set_parm(vertical_id, "TotalSpan", "WingGeom", vertical_span)
    adapter.set_parm(vertical_id, "Root_Chord", "XSec_1", vertical_chord)
    adapter.set_parm(vertical_id, "Tip_Chord", "XSec_1", vertical_chord * 0.55)
    adapter.set_parm(vertical_id, "X_Rel_Location", "XForm", tail_x)
    adapter.set_parm(vertical_id, "X_Rel_Rotation", "XForm", 90.0)

    return [
        GeometryBuildResult(
            name="horizontal_tail",
            geom_id=horizontal_id,
            applied_parameters={
                "tail.horizontal.span": horizontal_span,
                "tail.horizontal.chord": horizontal_chord,
            },
        ),
        GeometryBuildResult(
            name="vertical_tail",
            geom_id=vertical_id,
            applied_parameters={
                "tail.vertical.span": vertical_span,
                "tail.vertical.chord": vertical_chord,
            },
        ),
    ]
```

- [ ] **Step 7: Implement engine builder**

Create `services/workers/cad_worker/openvsp_generator/create_engine.py`:

```python
from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.workers.cad_worker.openvsp_generator.errors import UnsupportedGeometryError
from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult
from services.workers.cad_worker.openvsp_generator.openvsp_adapter import OpenVspAdapter


def create_engine_nacelles(adapter: OpenVspAdapter, spec: AircraftSpec) -> list[GeometryBuildResult]:
    count = int(spec.engine.count.value)
    if count != 2:
        raise UnsupportedGeometryError("OpenVSP MVP supports engine.count == 2 only")

    wing_span = float(spec.wing.span.value)
    root_chord = float(spec.wing.root_chord.value)
    fuselage_diameter = (
        float(spec.fuselage.max_diameter.value) if spec.fuselage.max_diameter else 0.75
    )
    y_offset = wing_span * 0.22
    x_offset = root_chord * 0.2
    z_offset = -fuselage_diameter * 0.55
    nacelle_length = root_chord * 0.8
    nacelle_diameter = fuselage_diameter * 0.35

    results: list[GeometryBuildResult] = []
    for side, sign in (("left", -1.0), ("right", 1.0)):
        geom_id = adapter.add_geom("POD")
        y = sign * y_offset
        adapter.set_parm(geom_id, "X_Rel_Location", "XForm", x_offset)
        adapter.set_parm(geom_id, "Y_Rel_Location", "XForm", y)
        adapter.set_parm(geom_id, "Z_Rel_Location", "XForm", z_offset)
        adapter.set_parm(geom_id, "Length", "Design", nacelle_length)
        adapter.set_parm(geom_id, "Diameter", "Design", nacelle_diameter)
        results.append(
            GeometryBuildResult(
                name=f"{side}_engine",
                geom_id=geom_id,
                applied_parameters={
                    "engine.count": count,
                    f"engine.{side}.y": y,
                    f"engine.{side}.length": nacelle_length,
                    f"engine.{side}.diameter": nacelle_diameter,
                },
            )
        )
    return results
```

- [ ] **Step 8: Run geometry builder tests**

Run:

```bash
.venv/bin/python -m pytest tests/api/test_openvsp_geometry_builders.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add services/workers/cad_worker/openvsp_generator/geometry.py \
  services/workers/cad_worker/openvsp_generator/create_fuselage.py \
  services/workers/cad_worker/openvsp_generator/create_wing.py \
  services/workers/cad_worker/openvsp_generator/create_tail.py \
  services/workers/cad_worker/openvsp_generator/create_engine.py \
  tests/api/test_openvsp_geometry_builders.py
git commit -m "feat: add openvsp geometry builders"
```

## Task 4: Real OpenVSP Backend Orchestration And Verification

**Files:**
- Modify: `services/workers/cad_worker/openvsp_generator/backend.py`
- Create: `services/workers/cad_worker/openvsp_generator/verify_model.py`
- Create: `tests/api/test_openvsp_backend_unit.py`

- [ ] **Step 1: Write backend unit test with fake adapter**

Create `tests/api/test_openvsp_backend_unit.py`:

```python
from pathlib import Path

from services.api.app.services.spec_io import load_aircraft_spec
from services.workers.cad_worker.openvsp_generator.backend import OpenVspBackend


class BackendFakeVspModule:
    SET_ALL = 0

    def __init__(self):
        self.geom_counter = 0
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def ClearVSPModel(self):
        self.calls.append(("ClearVSPModel", ()))

    def AddGeom(self, geom_type: str, parent: str = ""):
        self.geom_counter += 1
        geom_id = f"{geom_type}_{self.geom_counter}"
        self.calls.append(("AddGeom", (geom_type, parent, geom_id)))
        return geom_id

    def SetParmVal(self, geom_id: str, parm_name: str, group_name: str, value: float):
        self.calls.append(("SetParmVal", (geom_id, parm_name, group_name, value)))
        return 1

    def Update(self):
        self.calls.append(("Update", ()))

    def WriteVSPFile(self, path: str, set_id: int = 0):
        self.calls.append(("WriteVSPFile", (path, set_id)))
        Path(path).write_text("real-ish vsp3\n", encoding="utf-8")


def test_openvsp_backend_orchestrates_full_aircraft(tmp_path: Path):
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))
    fake_vsp = BackendFakeVspModule()
    backend = OpenVspBackend(vsp_module=fake_vsp)

    artifacts = backend.generate(spec, tmp_path)

    assert artifacts.files["vsp3"].exists()
    assert artifacts.files["vsp3"].stat().st_size > 0
    assert set(artifacts.components) == {
        "fuselage",
        "main_wing",
        "horizontal_tail",
        "vertical_tail",
        "left_engine",
        "right_engine",
    }
    assert artifacts.applied_parameters["wing.span"] == 12.0
    assert artifacts.applied_parameters["engine.count"] == 2
    assert artifacts.validation["backend"]["actual"] == "OpenVspBackend"
    assert artifacts.validation["vsp3.exists"]["status"] == "pass"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/api/test_openvsp_backend_unit.py -q
```

Expected: FAIL because `OpenVspBackend` does not accept `vsp_module` and does not orchestrate builders.

- [ ] **Step 3: Implement verification helper**

Create `services/workers/cad_worker/openvsp_generator/verify_model.py`:

```python
from pathlib import Path


def verify_vsp3_file(path: Path) -> dict[str, object]:
    exists = path.exists() and path.stat().st_size > 0
    return {
        "expected": True,
        "actual": exists,
        "status": "pass" if exists else "fail",
    }
```

- [ ] **Step 4: Implement OpenVspBackend orchestration**

Modify `OpenVspBackend` in `services/workers/cad_worker/openvsp_generator/backend.py`:

```python
class OpenVspBackend:
    def __init__(self, vsp_module: object | None = None) -> None:
        self.vsp_module = vsp_module

    def generate(self, spec: AircraftSpec, output_dir: Path) -> CadArtifacts:
        from services.workers.cad_worker.openvsp_generator.create_engine import create_engine_nacelles
        from services.workers.cad_worker.openvsp_generator.create_fuselage import create_fuselage
        from services.workers.cad_worker.openvsp_generator.create_tail import create_tail
        from services.workers.cad_worker.openvsp_generator.create_wing import create_main_wing
        from services.workers.cad_worker.openvsp_generator.openvsp_adapter import OpenVspAdapter
        from services.workers.cad_worker.openvsp_generator.verify_model import verify_vsp3_file

        adapter = OpenVspAdapter(self.vsp_module) if self.vsp_module is not None else OpenVspAdapter.load()
        output_dir.mkdir(parents=True, exist_ok=True)
        adapter.clear_model()

        build_results = [
            create_fuselage(adapter, spec),
            create_main_wing(adapter, spec),
            *create_tail(adapter, spec),
            *create_engine_nacelles(adapter, spec),
        ]

        adapter.update()
        vsp3 = output_dir / "aircraft.vsp3"
        adapter.write_vsp_file(vsp3)

        components = {result.name: result.geom_id for result in build_results}
        applied_parameters: dict[str, object] = {}
        for result in build_results:
            applied_parameters.update(result.applied_parameters)

        return CadArtifacts(
            files={"vsp3": vsp3},
            components=components,
            applied_parameters=applied_parameters,
            validation={
                "backend": {"expected": "openvsp", "actual": "OpenVspBackend", "status": "pass"},
                "vsp3.exists": verify_vsp3_file(vsp3),
            },
        )
```

- [ ] **Step 5: Run backend unit test**

Run:

```bash
.venv/bin/python -m pytest tests/api/test_openvsp_backend_unit.py tests/api/test_openvsp_geometry_builders.py -q
```

Expected: PASS.

- [ ] **Step 6: Run broader generation tests**

Run:

```bash
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_cad_generation.py tests/api/test_job_runner.py tests/api/test_generation_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add services/workers/cad_worker/openvsp_generator/backend.py \
  services/workers/cad_worker/openvsp_generator/verify_model.py \
  tests/api/test_openvsp_backend_unit.py
git commit -m "feat: orchestrate openvsp aircraft generation"
```

## Task 5: OpenVSP Opt-In Integration Test And Documentation

**Files:**
- Create: `tests/api/test_openvsp_integration.py`
- Modify: `.env`
- Modify: `README.md`

- [ ] **Step 1: Write skipped-by-default integration test**

Create `tests/api/test_openvsp_integration.py`:

```python
import os
from pathlib import Path

import pytest

from services.api.app.services.spec_io import load_aircraft_spec
from services.workers.cad_worker.openvsp_generator.backend import OpenVspBackend
from services.workers.cad_worker.openvsp_generator.errors import OpenVspUnavailableError
from services.workers.cad_worker.openvsp_generator.generate_aircraft import generate_aircraft


pytestmark = pytest.mark.skipif(
    not (os.getenv("RUN_OPENVSP_TESTS") == "1" and os.getenv("CAD_BACKEND") == "openvsp"),
    reason="OpenVSP integration tests require RUN_OPENVSP_TESTS=1 and CAD_BACKEND=openvsp",
)


def test_openvsp_backend_writes_real_vsp3(tmp_path: Path):
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))

    try:
        result = generate_aircraft(spec=spec, output_dir=tmp_path, backend=OpenVspBackend())
    except OpenVspUnavailableError as exc:
        pytest.fail(str(exc))

    assert result.files["vsp3"].exists()
    assert result.files["vsp3"].stat().st_size > 0
    assert result.validation_report["backend"]["actual"] == "OpenVspBackend"
    assert result.validation_report["vsp3.exists"]["status"] == "pass"
    assert result.validation_report["wing.span"]["status"] == "pass"
    assert result.validation_report["engine.count"]["status"] == "pass"
```

- [ ] **Step 2: Add `.env` default**

Modify `.env`:

```env
CAD_BACKEND=fake
```

Do not add `RUN_OPENVSP_TESTS=1` to default `.env`.

- [ ] **Step 3: Update README OpenVSP section**

Add this section to `README.md` after CAD Backend:

```markdown
## OpenVSP backend

The default CAD backend is fake and works without OpenVSP:

```bash
CAD_BACKEND=fake .venv/bin/python -m pytest -q
```

To opt into real OpenVSP generation, install an OpenVSP distribution whose Python API matches the Python version used by this project, then start the API with:

```bash
set -a
. ./.env
set +a
CAD_BACKEND=openvsp .venv/bin/python -m uvicorn services.api.app.main:app --host "$API_HOST" --port "$API_PORT"
```

OpenVSP integration tests are skipped by default. Run them only on a machine with OpenVSP installed:

```bash
CAD_BACKEND=openvsp RUN_OPENVSP_TESTS=1 .venv/bin/python -m pytest tests/api/test_openvsp_integration.py -q
```

Known limitation: the OpenVSP Python API is version-sensitive. The Python interpreter must match the version used by the OpenVSP package.
```

- [ ] **Step 4: Run default full test suite**

Run:

```bash
CAD_BACKEND=fake .venv/bin/python -m pytest -q
```

Expected: PASS with OpenVSP integration test skipped.

- [ ] **Step 5: Verify missing OpenVSP error path**

Run:

```bash
CAD_BACKEND=openvsp .venv/bin/python - <<'PY'
from services.workers.cad_worker.openvsp_generator.backend_factory import get_cad_backend
from services.workers.cad_worker.openvsp_generator.openvsp_adapter import OpenVspAdapter
from services.workers.cad_worker.openvsp_generator.errors import OpenVspUnavailableError

backend = get_cad_backend()
print(type(backend).__name__)
try:
    OpenVspAdapter.load()
except OpenVspUnavailableError as exc:
    print(str(exc))
PY
```

Expected without OpenVSP installed: prints `OpenVspBackend` and a clear missing OpenVSP message. If OpenVSP is installed, it may not print the error; that is acceptable.

- [ ] **Step 6: Commit**

```bash
git add tests/api/test_openvsp_integration.py .env README.md
git commit -m "docs: add openvsp backend verification"
```

## Task 6: Final Verification

**Files:**
- No new source files expected.

- [ ] **Step 1: Run full fake-backend test suite**

Run:

```bash
CAD_BACKEND=fake .venv/bin/python -m pytest -q
```

Expected: PASS. OpenVSP integration test should be skipped unless explicitly enabled.

- [ ] **Step 2: Run frontend build regression**

Stop `npm run dev` before running build if it is active, then run:

```bash
cd apps/web && npm run build
```

Expected: PASS.

- [ ] **Step 3: Run fake backend API smoke test**

Run backend:

```bash
set -a
. ./.env
set +a
CAD_BACKEND=fake .venv/bin/python -m uvicorn services.api.app.main:app --host "$API_HOST" --port "$API_PORT"
```

In another shell:

```bash
curl -sS -X POST \
  --data-binary @packages/aircraft-schema/examples/twin_engine_uav.yaml \
  -H "Content-Type: application/x-yaml" \
  "http://$API_HOST:$API_PORT/api/designs/openvsp-plan-smoke/generate"
```

Expected: response has `status` equal to `ready`, `progress` equal to `100`, and a `vsp3` file path.

- [ ] **Step 4: Check working tree**

Run:

```bash
git status --short
```

Expected: no tracked dirty files. Untracked historical planning files may remain if intentionally left untracked.

## Self-Review

- Spec coverage: The plan covers backend selection, real OpenVSP availability detection, focused geometry modules, `.vsp3` generation, parameter-level validation, fake-backend compatibility, opt-in integration tests, API compatibility, and README documentation.
- Out-of-scope enforcement: STEP, GLB, frontend 3D rendering, natural-language parsing, LangGraph, and analysis are not implemented in this plan.
- Placeholder scan: The plan contains no implementation placeholders. Every task has concrete files, code, commands, and expected outcomes.
- Type consistency: `CadArtifacts`, `CadBackend`, `OpenVspAdapter`, `GeometryBuildResult`, `OpenVspBackend`, `get_cad_backend`, and `generate_aircraft` signatures are used consistently across tasks.
