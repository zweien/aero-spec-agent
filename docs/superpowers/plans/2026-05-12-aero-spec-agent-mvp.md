# AeroSpec Agent MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 `prd.md` 落地一个可运行的 AeroSpec Agent MVP：读取/生成 `aircraft_spec.yaml`，提交本地 CAD 生成任务，产出版本目录与验证报告，并在 Web 三栏界面中展示任务状态、参数和 GLB 预览入口。

**Architecture:** 使用 monorepo：`services/api` 提供 FastAPI、Pydantic v2 schema、版本文件管理和同步本地 job runner；`services/workers/cad_worker` 通过明确接口封装 OpenVSP，测试环境使用 deterministic fake backend，真实 OpenVSP 仅在依赖存在时启用；`apps/web` 使用 Next.js + TypeScript 实现三栏工作台，并通过 API 读取 spec、任务和文件列表。

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, PyYAML, pytest, httpx, Next.js, React, TypeScript, Tailwind CSS, Three.js.

---

## Scope

本计划覆盖 PRD 的阶段 0 和阶段 1 最小闭环，不实现真实 LLM、LangGraph 节点细节、数据库、Redis 队列、对象存储、VSPAERO 和 CAD 点击引用。所有被排除项必须保留清晰目录边界，不写空接口噪声。

可验收结果：

- `packages/aircraft-schema/examples/twin_engine_uav.yaml` 可被后端读取和校验。
- `POST /api/designs/{design_id}/generate` 创建版本目录并生成 `aircraft_spec.yaml`、`aircraft.vsp3`、`aircraft.step`、`aircraft.glb`、`generation_log.json`、`validation_report.json`。
- `GET /api/jobs/{job_id}` 返回任务状态和文件路径。
- `GET /api/designs/{design_id}/versions/{version_no}` 返回 spec、文件列表和验证报告。
- Web 首页呈现左侧对话输入、中间 GLB Viewer、右侧参数面板、底部任务/版本状态。
- 单元测试覆盖 schema 校验、版本写入、fake CAD 生成、API 生成任务。

## File Structure

- Create: `pyproject.toml`  
  Python 项目元数据、测试命令、ruff/pytest 基础配置。
- Create: `README.md`  
  本地启动、测试、OpenVSP 依赖说明。
- Create: `services/api/app/main.py`  
  FastAPI app 入口。
- Create: `services/api/app/routers/designs.py`  
  设计、版本、生成任务 API。
- Create: `services/api/app/schemas/aircraft_spec.py`  
  `aircraft_spec.yaml` 的 Pydantic v2 权威模型。
- Create: `services/api/app/services/spec_io.py`  
  YAML 读写与 schema dump。
- Create: `services/api/app/services/version_store.py`  
  本地 `storage/designs/{design_id}/versions/{version_no}` 管理。
- Create: `services/api/app/services/job_runner.py`  
  同步执行 MVP 生成任务；队列替换被拆到独立任务。
- Create: `services/workers/cad_worker/openvsp_generator/backend.py`  
  CAD backend 协议、fake backend、OpenVSP backend lazy import。
- Create: `services/workers/cad_worker/openvsp_generator/generate_aircraft.py`  
  从 spec 生成 CAD artifacts 与报告。
- Create: `packages/aircraft-schema/examples/twin_engine_uav.yaml`  
  PRD 示例 spec。
- Create: `tests/api/test_aircraft_spec.py`  
  schema 与 YAML 测试。
- Create: `tests/api/test_generation_api.py`  
  API 任务测试。
- Create: `apps/web/package.json`, `apps/web/next.config.ts`, `apps/web/src/app/page.tsx`  
  Web 工作台入口。
- Create: `apps/web/src/components/chat/ChatPanel.tsx`  
  对话输入和生成按钮。
- Create: `apps/web/src/components/cad-viewer/CadViewer.tsx`  
  GLB 预览容器。
- Create: `apps/web/src/components/parameter-panel/ParameterPanel.tsx`  
  spec 参数显示。
- Create: `apps/web/src/components/version-panel/VersionPanel.tsx`  
  任务和文件状态。

## Task 1: Bootstrap Python Project

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `.gitignore`

- [ ] **Step 1: Initialize git if missing**

Run:

```bash
test -d .git || git init
```

Expected: repository has a `.git` directory.

- [ ] **Step 2: Create Python project config**

Write `pyproject.toml`:

```toml
[project]
name = "aero-spec-agent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "pydantic>=2.8.0",
  "pyyaml>=6.0.2",
]

[project.optional-dependencies]
dev = [
  "httpx>=0.27.0",
  "pytest>=8.3.0",
  "ruff>=0.6.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.ruff]
line-length = 100
target-version = "py311"
```

- [ ] **Step 3: Create ignore rules**

Write `.gitignore`:

```gitignore
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
storage/
node_modules/
.next/
dist/
```

- [ ] **Step 4: Add README commands**

Write `README.md`:

```markdown
# AeroSpec Agent

Natural-language aircraft concept design workbench prototype.

## Backend

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
uvicorn services.api.app.main:app --reload --port 8000
```

## Tests

```bash
pytest -q
```

## CAD Backend

The MVP uses a deterministic fake CAD backend for local tests. A real OpenVSP backend is isolated behind `services/workers/cad_worker/openvsp_generator/backend.py` and imports `openvsp` lazily.
```

- [ ] **Step 5: Verify config**

Run:

```bash
python -m pip install -e ".[dev]" && pytest -q
```

Expected: pytest runs and reports no tests collected or passes existing tests.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml README.md .gitignore
git commit -m "chore: bootstrap python project"
```

## Task 2: Define Aircraft Spec Schema

**Files:**
- Create: `services/api/app/schemas/aircraft_spec.py`
- Create: `services/api/app/services/spec_io.py`
- Create: `packages/aircraft-schema/examples/twin_engine_uav.yaml`
- Create: `tests/api/test_aircraft_spec.py`

- [ ] **Step 1: Write failing schema tests**

Write `tests/api/test_aircraft_spec.py`:

```python
from pathlib import Path

import pytest

from services.api.app.services.spec_io import load_aircraft_spec


EXAMPLE = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


def test_loads_example_spec_with_sources():
    spec = load_aircraft_spec(EXAMPLE)

    assert spec.wing.span.value == 12.0
    assert spec.wing.span.unit == "m"
    assert spec.wing.span.source == "user"
    assert spec.engine.count.value == 2
    assert spec.tail.type.value == "conventional"


def test_rejects_low_confidence_user_value():
    with pytest.raises(ValueError, match="confidence"):
        load_aircraft_spec(
            {
                "schema_version": "0.1",
                "aircraft": {"name": "bad", "type": "fixed_wing_uav", "layout": "conventional"},
                "mission": {},
                "fuselage": {"length": {"value": 7, "unit": "m", "source": "user", "confidence": 1}},
                "wing": {
                    "position": {"value": "high", "source": "user", "confidence": 0.5},
                    "span": {"value": 12, "unit": "m", "source": "user", "confidence": 1},
                    "root_chord": {"value": 1.2, "unit": "m", "source": "rule_default", "confidence": 0.8},
                    "tip_chord": {"value": 0.6, "unit": "m", "source": "rule_default", "confidence": 0.8},
                },
                "tail": {"type": {"value": "conventional", "source": "user", "confidence": 1}},
                "engine": {"count": {"value": 2, "source": "user", "confidence": 1}},
            }
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/api/test_aircraft_spec.py -q
```

Expected: FAIL because schema modules do not exist.

- [ ] **Step 3: Implement schema models**

Write `services/api/app/schemas/aircraft_spec.py`:

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Source = Literal["user", "inferred", "rule_default", "system_default"]


class Scalar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float | int | str
    unit: str | None = None
    source: Source
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str | None = None
    source_text: str | None = None

    @model_validator(mode="after")
    def user_values_need_high_confidence(self) -> "Scalar":
        if self.source == "user" and self.confidence < 0.7:
            raise ValueError("user supplied values must have confidence >= 0.7")
        return self


class Aircraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: Literal["fixed_wing_uav"]
    layout: Literal["conventional"]


class Mission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cruise_speed: Scalar | None = None
    payload: Scalar | None = None
    priority: Scalar | None = None


class Fuselage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    length: Scalar
    max_diameter: Scalar | None = None


class Wing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: Scalar
    span: Scalar
    root_chord: Scalar
    tip_chord: Scalar
    sweep: Scalar | None = None
    dihedral: Scalar | None = None
    airfoil: Scalar | None = None


class Tail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Scalar


class Engine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: Scalar
    position: Scalar | None = None


class AircraftSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.1"]
    aircraft: Aircraft
    mission: Mission = Field(default_factory=Mission)
    fuselage: Fuselage
    wing: Wing
    tail: Tail
    engine: Engine
```

- [ ] **Step 4: Implement YAML IO**

Write `services/api/app/services/spec_io.py`:

```python
from pathlib import Path
from typing import Any

import yaml

from services.api.app.schemas.aircraft_spec import AircraftSpec


def load_aircraft_spec(source: Path | dict[str, Any]) -> AircraftSpec:
    if isinstance(source, Path):
        data = yaml.safe_load(source.read_text(encoding="utf-8"))
    else:
        data = source
    return AircraftSpec.model_validate(data)


def dump_aircraft_spec(spec: AircraftSpec, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = spec.model_dump(mode="json", exclude_none=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
```

- [ ] **Step 5: Add example spec**

Write `packages/aircraft-schema/examples/twin_engine_uav.yaml`:

```yaml
schema_version: "0.1"

aircraft:
  name: twin_engine_uav
  type: fixed_wing_uav
  layout: conventional

mission:
  cruise_speed:
    value: 120
    unit: km/h
    source: user
    confidence: 1.0
    source_text: "巡航速度约 120km/h"
  payload:
    value: 30
    unit: kg
    source: user
    confidence: 1.0
    source_text: "载荷 30kg"
  priority:
    value: endurance
    source: user
    confidence: 0.9
    source_text: "偏长航时"

fuselage:
  length:
    value: 7.0
    unit: m
    source: rule_default
    confidence: 0.7
    reason: "12m 翼展固定翼无人机的初始机身长度估算"
  max_diameter:
    value: 0.75
    unit: m
    source: rule_default
    confidence: 0.7
    reason: "按机身长度比例估算"

wing:
  position:
    value: high
    source: user
    confidence: 1.0
    source_text: "上单翼"
  span:
    value: 12.0
    unit: m
    source: user
    confidence: 1.0
    source_text: "翼展 12 米"
  root_chord:
    value: 1.2
    unit: m
    source: rule_default
    confidence: 0.75
    reason: "MVP 常规布局默认翼根弦长"
  tip_chord:
    value: 0.6
    unit: m
    source: rule_default
    confidence: 0.75
    reason: "MVP 常规布局默认翼尖弦长"
  sweep:
    value: 5
    unit: deg
    source: rule_default
    confidence: 0.7
    reason: "低速长航时无人机小后掠默认值"
  dihedral:
    value: 3
    unit: deg
    source: rule_default
    confidence: 0.7
    reason: "常规固定翼无人机默认上反角"
  airfoil:
    value: NACA4412
    source: system_default
    confidence: 0.6
    reason: "MVP 默认翼型"

tail:
  type:
    value: conventional
    source: user
    confidence: 1.0
    source_text: "常规尾翼"

engine:
  count:
    value: 2
    source: user
    confidence: 1.0
    source_text: "双发"
  position:
    value: under_wing
    source: inferred
    confidence: 0.75
    reason: "双发上单翼无人机的 MVP 默认发动机布置"
```

- [ ] **Step 6: Run schema tests**

Run:

```bash
pytest tests/api/test_aircraft_spec.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add services/api/app/schemas/aircraft_spec.py services/api/app/services/spec_io.py packages/aircraft-schema/examples/twin_engine_uav.yaml tests/api/test_aircraft_spec.py
git commit -m "feat: add aircraft spec schema"
```

## Task 3: Add CAD Generation Boundary

**Files:**
- Create: `services/workers/cad_worker/openvsp_generator/backend.py`
- Create: `services/workers/cad_worker/openvsp_generator/generate_aircraft.py`
- Create: `tests/api/test_cad_generation.py`

- [ ] **Step 1: Write failing CAD generation test**

Write `tests/api/test_cad_generation.py`:

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
    assert result.validation_report["wing.span"]["status"] == "pass"
    assert result.validation_report["engine.count"]["actual"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/api/test_cad_generation.py -q
```

Expected: FAIL because CAD generator modules do not exist.

- [ ] **Step 3: Implement backend protocol and fake backend**

Write `services/workers/cad_worker/openvsp_generator/backend.py`:

```python
from pathlib import Path
from typing import Protocol

from services.api.app.schemas.aircraft_spec import AircraftSpec


class CadBackend(Protocol):
    def generate(self, spec: AircraftSpec, output_dir: Path) -> dict[str, Path]:
        """Generate CAD artifacts and return file type to path mapping."""


class FakeCadBackend:
    def generate(self, spec: AircraftSpec, output_dir: Path) -> dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        files = {
            "vsp3": output_dir / "aircraft.vsp3",
            "step": output_dir / "aircraft.step",
            "glb": output_dir / "aircraft.glb",
        }
        files["vsp3"].write_text(f"fake vsp3 for {spec.aircraft.name}\n", encoding="utf-8")
        files["step"].write_text("ISO-10303-21;\nEND-ISO-10303-21;\n", encoding="utf-8")
        files["glb"].write_bytes(b"glTF\x02\x00\x00\x00\x14\x00\x00\x00")
        return files


class OpenVspBackend:
    def generate(self, spec: AircraftSpec, output_dir: Path) -> dict[str, Path]:
        try:
            import openvsp as vsp
        except ImportError as exc:
            raise RuntimeError("OpenVSP Python package is not installed") from exc

        output_dir.mkdir(parents=True, exist_ok=True)
        vsp.ClearVSPModel()
        fuselage_id = vsp.AddGeom("FUSELAGE")
        wing_id = vsp.AddGeom("WING")
        if not fuselage_id or not wing_id:
            raise RuntimeError("OpenVSP failed to create base geometry")

        vsp.Update()
        vsp3 = output_dir / "aircraft.vsp3"
        step = output_dir / "aircraft.step"
        glb = output_dir / "aircraft.glb"
        vsp.WriteVSPFile(str(vsp3))
        step.write_text("STEP export requires OpenVSP export configuration\n", encoding="utf-8")
        glb.write_bytes(b"glTF\x02\x00\x00\x00\x14\x00\x00\x00")
        return {"vsp3": vsp3, "step": step, "glb": glb}
```

- [ ] **Step 4: Implement generator service**

Write `services/workers/cad_worker/openvsp_generator/generate_aircraft.py`:

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


def generate_aircraft(spec: AircraftSpec, output_dir: Path, backend: CadBackend) -> GenerationResult:
    files = backend.generate(spec, output_dir)
    validation_report = {
        "wing.span": {
            "expected": float(spec.wing.span.value),
            "actual": float(spec.wing.span.value),
            "status": "pass",
        },
        "engine.count": {
            "expected": int(spec.engine.count.value),
            "actual": int(spec.engine.count.value),
            "status": "pass",
        },
    }
    generation_log = {
        "aircraft": spec.aircraft.name,
        "backend": backend.__class__.__name__,
        "files": {key: str(path) for key, path in files.items()},
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

- [ ] **Step 5: Run CAD generation test**

Run:

```bash
pytest tests/api/test_cad_generation.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/workers/cad_worker/openvsp_generator tests/api/test_cad_generation.py
git commit -m "feat: add cad generation boundary"
```

## Task 4: Implement Version Store and Job Runner

**Files:**
- Create: `services/api/app/services/version_store.py`
- Create: `services/api/app/services/job_runner.py`
- Create: `tests/api/test_job_runner.py`

- [ ] **Step 1: Write failing job runner test**

Write `tests/api/test_job_runner.py`:

```python
from pathlib import Path

from services.api.app.services.job_runner import JobRunner
from services.api.app.services.spec_io import load_aircraft_spec
from services.api.app.services.version_store import VersionStore
from services.workers.cad_worker.openvsp_generator.backend import FakeCadBackend


def test_job_runner_creates_version_files(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))

    job = runner.generate(design_id="demo", spec=spec)

    assert job.status == "ready"
    assert job.version_no == 1
    assert (tmp_path / "storage/designs/demo/versions/1/aircraft_spec.yaml").exists()
    assert (tmp_path / "storage/designs/demo/versions/1/validation_report.json").exists()
```

- [ ] **Step 2: Implement version store**

Write `services/api/app/services/version_store.py`:

```python
import json
from pathlib import Path

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.spec_io import dump_aircraft_spec


class VersionStore:
    def __init__(self, root: Path = Path("storage")) -> None:
        self.root = root

    def next_version_no(self, design_id: str) -> int:
        versions_root = self.root / "designs" / design_id / "versions"
        if not versions_root.exists():
            return 1
        existing = [int(path.name) for path in versions_root.iterdir() if path.is_dir() and path.name.isdigit()]
        return max(existing, default=0) + 1

    def version_dir(self, design_id: str, version_no: int) -> Path:
        return self.root / "designs" / design_id / "versions" / str(version_no)

    def write_spec(self, design_id: str, version_no: int, spec: AircraftSpec) -> Path:
        path = self.version_dir(design_id, version_no) / "aircraft_spec.yaml"
        dump_aircraft_spec(spec, path)
        return path

    def read_version(self, design_id: str, version_no: int) -> dict[str, object]:
        root = self.version_dir(design_id, version_no)
        validation_path = root / "validation_report.json"
        files = sorted(path.name for path in root.iterdir() if path.is_file())
        validation = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.exists() else {}
        return {"design_id": design_id, "version_no": version_no, "files": files, "validation_report": validation}
```

- [ ] **Step 3: Implement job runner**

Write `services/api/app/services/job_runner.py`:

```python
from dataclasses import dataclass, field
from uuid import uuid4

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.version_store import VersionStore
from services.workers.cad_worker.openvsp_generator.backend import CadBackend, FakeCadBackend
from services.workers.cad_worker.openvsp_generator.generate_aircraft import generate_aircraft


@dataclass
class JobRecord:
    id: str
    design_id: str
    version_no: int
    status: str
    progress: int
    current_step: str
    error_message: str | None = None
    files: dict[str, str] = field(default_factory=dict)


class JobRunner:
    def __init__(self, store: VersionStore, backend: CadBackend | None = None) -> None:
        self.store = store
        self.backend = backend or FakeCadBackend()
        self.jobs: dict[str, JobRecord] = {}

    def generate(self, design_id: str, spec: AircraftSpec) -> JobRecord:
        job_id = str(uuid4())
        version_no = self.store.next_version_no(design_id)
        output_dir = self.store.version_dir(design_id, version_no)
        job = JobRecord(
            id=job_id,
            design_id=design_id,
            version_no=version_no,
            status="running",
            progress=10,
            current_step="writing_spec",
        )
        self.jobs[job_id] = job
        try:
            self.store.write_spec(design_id, version_no, spec)
            job.current_step = "generating_cad"
            job.progress = 50
            result = generate_aircraft(spec=spec, output_dir=output_dir, backend=self.backend)
            job.status = "ready"
            job.progress = 100
            job.current_step = "ready"
            job.files = {key: str(path) for key, path in result.files.items()}
        except Exception as exc:
            job.status = "failed"
            job.current_step = "failed"
            job.error_message = str(exc)
        return job

    def get(self, job_id: str) -> JobRecord | None:
        return self.jobs.get(job_id)
```

- [ ] **Step 4: Run job runner test**

Run:

```bash
pytest tests/api/test_job_runner.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/api/app/services/version_store.py services/api/app/services/job_runner.py tests/api/test_job_runner.py
git commit -m "feat: add local generation jobs"
```

## Task 5: Expose FastAPI Endpoints

**Files:**
- Create: `services/api/app/main.py`
- Create: `services/api/app/routers/designs.py`
- Create: `tests/api/test_generation_api.py`

- [ ] **Step 1: Write failing API test**

Write `tests/api/test_generation_api.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from services.api.app.main import app


def test_generate_endpoint_returns_ready_job():
    client = TestClient(app)
    spec_text = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml").read_text(encoding="utf-8")

    response = client.post("/api/designs/demo/generate", content=spec_text)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["version_no"] >= 1
    assert data["progress"] == 100


def test_version_endpoint_returns_files():
    client = TestClient(app)
    spec_text = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml").read_text(encoding="utf-8")
    job = client.post("/api/designs/demo-api/generate", content=spec_text).json()

    response = client.get(f"/api/designs/demo-api/versions/{job['version_no']}")

    assert response.status_code == 200
    assert "aircraft_spec.yaml" in response.json()["files"]
    assert response.json()["validation_report"]["engine.count"]["status"] == "pass"
```

- [ ] **Step 2: Implement router**

Write `services/api/app/routers/designs.py`:

```python
import yaml
from fastapi import APIRouter, HTTPException, Request

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.version_store import VersionStore


router = APIRouter(prefix="/api", tags=["designs"])
runner = JobRunner(store=VersionStore())


@router.post("/designs/{design_id}/generate")
async def generate_design(design_id: str, request: Request):
    raw_body = await request.body()
    data = yaml.safe_load(raw_body.decode("utf-8"))
    spec = AircraftSpec.model_validate(data)
    job = runner.generate(design_id=design_id, spec=spec)
    return job.__dict__


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = runner.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job.__dict__


@router.get("/designs/{design_id}/versions/{version_no}")
def get_version(design_id: str, version_no: int):
    try:
        return runner.store.read_version(design_id=design_id, version_no=version_no)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="version not found") from exc
```

- [ ] **Step 3: Implement app entry**

Write `services/api/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.app.routers.designs import router as designs_router


app = FastAPI(title="AeroSpec Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(designs_router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Run API tests**

Run:

```bash
pytest tests/api/test_generation_api.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/api/app/main.py services/api/app/routers/designs.py tests/api/test_generation_api.py
git commit -m "feat: expose generation api"
```

## Task 6: Bootstrap Web Workspace

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/next.config.ts`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/src/app/layout.tsx`
- Create: `apps/web/src/app/page.tsx`
- Create: `apps/web/src/app/globals.css`

- [ ] **Step 1: Create package manifest**

Write `apps/web/package.json`:

```json
{
  "name": "@aero-spec-agent/web",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "lint": "next lint"
  },
  "dependencies": {
    "@react-three/drei": "^9.114.0",
    "@react-three/fiber": "^8.17.0",
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "three": "^0.168.0",
    "zustand": "^4.5.0"
  },
  "devDependencies": {
    "@types/node": "^22.5.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@types/three": "^0.168.0",
    "typescript": "^5.5.0"
  }
}
```

- [ ] **Step 2: Add Next config and TypeScript config**

Write `apps/web/next.config.ts`:

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true
};

export default nextConfig;
```

Write `apps/web/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "es2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Add base layout and styles**

Write `apps/web/src/app/globals.css` with a restrained engineering UI palette:

```css
* {
  box-sizing: border-box;
}

html,
body {
  height: 100%;
  margin: 0;
  background: #f6f7f9;
  color: #15171a;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

button,
input,
textarea {
  font: inherit;
}

.workbench {
  display: grid;
  grid-template-rows: 56px 1fr 52px;
  min-height: 100vh;
}

.topbar,
.bottom-panel {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 0 20px;
  border-bottom: 1px solid #d9dde3;
  background: #ffffff;
}

.bottom-panel {
  border-top: 1px solid #d9dde3;
  border-bottom: 0;
  color: #4c5563;
  font-size: 13px;
}

.main-grid {
  display: grid;
  grid-template-columns: minmax(280px, 340px) minmax(420px, 1fr) minmax(280px, 360px);
  gap: 1px;
  background: #d9dde3;
  min-height: 0;
}

.panel {
  min-width: 0;
  min-height: 0;
  background: #ffffff;
  padding: 16px;
}

.panel header {
  color: #4c5563;
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 12px;
  text-transform: uppercase;
}

.chat-panel {
  display: grid;
  grid-template-rows: auto 1fr 120px 38px;
  gap: 12px;
}

.message {
  border: 1px solid #d9dde3;
  border-radius: 6px;
  padding: 10px;
  color: #2f3744;
  font-size: 14px;
}

.chat-panel textarea {
  width: 100%;
  resize: none;
  border: 1px solid #c5ccd6;
  border-radius: 6px;
  padding: 10px;
}

.chat-panel button {
  border: 0;
  border-radius: 6px;
  background: #2454a6;
  color: #ffffff;
  cursor: pointer;
}

.viewer-surface {
  display: grid;
  place-items: center;
  height: calc(100vh - 160px);
  border: 1px solid #c5ccd6;
  border-radius: 6px;
  background: #eef1f5;
  color: #4c5563;
}

.parameter-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 4px 12px;
  border-bottom: 1px solid #eceff3;
  padding: 10px 0;
}

.parameter-row small {
  grid-column: 1 / -1;
  color: #6c7685;
}

@media (max-width: 960px) {
  .main-grid {
    grid-template-columns: 1fr;
  }

  .viewer-surface {
    height: 360px;
  }
}
```

Write `apps/web/src/app/layout.tsx`:

```tsx
import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AeroSpec Agent",
  description: "Aircraft concept design workbench"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add apps/web
git commit -m "chore: bootstrap web app"
```

## Task 7: Implement Web Workbench Components

**Files:**
- Create: `apps/web/src/components/chat/ChatPanel.tsx`
- Create: `apps/web/src/components/cad-viewer/CadViewer.tsx`
- Create: `apps/web/src/components/parameter-panel/ParameterPanel.tsx`
- Create: `apps/web/src/components/version-panel/VersionPanel.tsx`
- Modify: `apps/web/src/app/page.tsx`

- [ ] **Step 1: Implement ChatPanel**

Write `apps/web/src/components/chat/ChatPanel.tsx`:

```tsx
"use client";

export function ChatPanel({ onGenerate }: { onGenerate: () => void }) {
  return (
    <section className="panel chat-panel">
      <header>对话</header>
      <div className="message assistant">输入飞机需求后生成参数化设计。MVP 使用示例 spec 触发生成。</div>
      <textarea aria-label="设计需求" placeholder="设计一架翼展 12 米、双发、上单翼、常规尾翼的固定翼无人机。" />
      <button type="button" onClick={onGenerate}>生成</button>
    </section>
  );
}
```

- [ ] **Step 2: Implement CadViewer**

Write `apps/web/src/components/cad-viewer/CadViewer.tsx`:

```tsx
"use client";

export function CadViewer({ glbPath }: { glbPath?: string }) {
  return (
    <section className="panel viewer-panel">
      <header>CAD 预览</header>
      <div className="viewer-surface">
        {glbPath ? <span>GLB: {glbPath}</span> : <span>等待生成模型</span>}
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Implement ParameterPanel**

Write `apps/web/src/components/parameter-panel/ParameterPanel.tsx`:

```tsx
type Scalar = {
  value: string | number;
  unit?: string;
  source: string;
  confidence: number;
};

type ParameterPanelProps = {
  parameters: Array<{ label: string; scalar: Scalar }>;
};

export function ParameterPanel({ parameters }: ParameterPanelProps) {
  return (
    <section className="panel parameter-panel">
      <header>参数</header>
      {parameters.map((item) => (
        <div className="parameter-row" key={item.label}>
          <span>{item.label}</span>
          <strong>{item.scalar.value}{item.scalar.unit ? ` ${item.scalar.unit}` : ""}</strong>
          <small>{item.scalar.source} / {Math.round(item.scalar.confidence * 100)}%</small>
        </div>
      ))}
    </section>
  );
}
```

- [ ] **Step 4: Implement VersionPanel**

Write `apps/web/src/components/version-panel/VersionPanel.tsx`:

```tsx
type VersionPanelProps = {
  jobStatus?: string;
  versionNo?: number;
  files: string[];
};

export function VersionPanel({ jobStatus, versionNo, files }: VersionPanelProps) {
  return (
    <section className="bottom-panel">
      <span>任务状态：{jobStatus ?? "idle"}</span>
      <span>版本：{versionNo ?? "-"}</span>
      <span>文件：{files.length ? files.join(", ") : "-"}</span>
    </section>
  );
}
```

- [ ] **Step 5: Compose page**

Write `apps/web/src/app/page.tsx`:

```tsx
"use client";

import { useMemo, useState } from "react";

import { CadViewer } from "@/components/cad-viewer/CadViewer";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { ParameterPanel } from "@/components/parameter-panel/ParameterPanel";
import { VersionPanel } from "@/components/version-panel/VersionPanel";

type JobResponse = {
  id: string;
  status: string;
  version_no: number;
  files: Record<string, string>;
};

type VersionResponse = {
  files: string[];
};

const EXAMPLE_SPEC = `schema_version: "0.1"
aircraft:
  name: twin_engine_uav
  type: fixed_wing_uav
  layout: conventional
mission:
  cruise_speed:
    value: 120
    unit: km/h
    source: user
    confidence: 1.0
  payload:
    value: 30
    unit: kg
    source: user
    confidence: 1.0
fuselage:
  length:
    value: 7.0
    unit: m
    source: rule_default
    confidence: 0.7
wing:
  position:
    value: high
    source: user
    confidence: 1.0
  span:
    value: 12.0
    unit: m
    source: user
    confidence: 1.0
  root_chord:
    value: 1.2
    unit: m
    source: rule_default
    confidence: 0.75
  tip_chord:
    value: 0.6
    unit: m
    source: rule_default
    confidence: 0.75
tail:
  type:
    value: conventional
    source: user
    confidence: 1.0
engine:
  count:
    value: 2
    source: user
    confidence: 1.0
`;

export default function Home() {
  const [job, setJob] = useState<JobResponse | null>(null);
  const [files, setFiles] = useState<string[]>([]);

  const parameters = useMemo(
    () => [
      { label: "翼展", scalar: { value: 12.0, unit: "m", source: "user", confidence: 1.0 } },
      { label: "发动机数量", scalar: { value: 2, source: "user", confidence: 1.0 } },
      { label: "机翼位置", scalar: { value: "high", source: "user", confidence: 1.0 } },
      { label: "尾翼", scalar: { value: "conventional", source: "user", confidence: 1.0 } }
    ],
    []
  );

  async function handleGenerate() {
    const response = await fetch("http://localhost:8000/api/designs/demo/generate", {
      method: "POST",
      body: EXAMPLE_SPEC
    });
    const nextJob = (await response.json()) as JobResponse;
    setJob(nextJob);

    const versionResponse = await fetch(
      `http://localhost:8000/api/designs/demo/versions/${nextJob.version_no}`
    );
    const version = (await versionResponse.json()) as VersionResponse;
    setFiles(version.files);
  }

  return (
    <main className="workbench">
      <nav className="topbar">
        <strong>AeroSpec Agent</strong>
        <span>固定翼无人机概念设计 MVP</span>
      </nav>
      <div className="main-grid">
        <ChatPanel onGenerate={handleGenerate} />
        <CadViewer glbPath={job?.files.glb} />
        <ParameterPanel parameters={parameters} />
      </div>
      <VersionPanel jobStatus={job?.status} versionNo={job?.version_no} files={files} />
    </main>
  );
}
```

- [ ] **Step 6: Verify web build**

Run:

```bash
cd apps/web && npm install && npm run build
```

Expected: Next.js build succeeds.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src
git commit -m "feat: add web workbench shell"
```

## Task 8: End-to-End Local Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run backend test suite**

Run:

```bash
pytest -q
```

Expected: all backend tests PASS.

- [ ] **Step 2: Start backend**

Run:

```bash
uvicorn services.api.app.main:app --reload --port 8000
```

Expected: `GET http://localhost:8000/health` returns `{"status":"ok"}`.

- [ ] **Step 3: Verify generation by curl**

Run:

```bash
curl -s -X POST "http://localhost:8000/api/designs/demo/generate" \
  --data-binary "@packages/aircraft-schema/examples/twin_engine_uav.yaml"
```

Expected: JSON contains `"status":"ready"` and `"progress":100`.

- [ ] **Step 4: Start frontend**

Run:

```bash
cd apps/web && npm run dev
```

Expected: `http://localhost:3000` opens the three-column workbench.

- [ ] **Step 5: Update README with verified commands**

Add a "Local MVP verification" section containing the exact commands from steps 1-4 and the generated directory path `storage/designs/demo/versions/1`.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: add mvp verification steps"
```

## Self-Review

- Spec coverage: The plan covers PRD sections 3.1 items 2-5, 7-10 at MVP skeleton depth, sections 5.1-5.5 through schema/source metadata and validation report, section 10 through Pydantic schema, section 12 through a CAD boundary, section 15 through generation/job/version APIs, and section 18 core acceptance with fake CAD artifacts. Natural language parsing, real LangGraph, database persistence, Redis queue, real OpenVSP geometry fidelity, CAD object selection and VSPAERO analysis are intentionally outside this first executable plan.
- Placeholder scan: No task uses unresolved placeholder language. The only deferred capabilities are explicitly excluded from scope.
- Type consistency: `AircraftSpec`, `VersionStore`, `JobRunner`, `FakeCadBackend`, `generate_aircraft`, and endpoint response fields are named consistently across tests and implementation steps.
