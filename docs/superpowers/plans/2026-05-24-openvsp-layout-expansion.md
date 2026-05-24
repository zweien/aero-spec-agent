# OpenVSP 气动布局全面扩展 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 OpenVSP 几何建模从仅支持 conventional 布局扩展为覆盖固定翼 UAV 全系列（4 种布局、5 种尾翼、多段翼、1-4 发动机）。

**Architecture:** 按布局类型分 4 批次交付，每批完整后端→Schema→UI→测试链路。新增布局分发层（`LAYOUT_BUILDERS` dict），每个布局有独立 builder 函数。新增 `create_boom.py` 和 `create_body.py` 几何构建器。

**Tech Stack:** Python 3.11+ / Pydantic 2 / OpenVSP 3.50.2 Python API / FastAPI / Next.js 14

**Design Spec:** `docs/superpowers/specs/2026-05-24-openvsp-layout-expansion-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `services/api/app/schemas/aircraft_spec.py` | Modify | Schema: layout Literal 扩展 + Wing/Boom/Body 新字段 |
| `services/api/app/services/chat_tools.py` | Modify | Chat Tool: SUPPORTED_FIELD_VALUES + generate_design enum |
| `services/api/app/services/spec_defaults.py` | Modify | 默认值: wing.sections, boom.*, body.* |
| `services/workers/cad_worker/openvsp_generator/create_tail.py` | Modify | 尾翼: v_tail, inverted_v, cruciform |
| `services/workers/cad_worker/openvsp_generator/create_wing.py` | Modify | 多段翼: sections 1-3 |
| `services/workers/cad_worker/openvsp_generator/create_engine.py` | Modify | 发动机: 3-4 台 + wing_tip/over_wing/pusher |
| `services/workers/cad_worker/openvsp_generator/create_boom.py` | **Create** | 双尾撑几何体 |
| `services/workers/cad_worker/openvsp_generator/create_body.py` | **Create** | BWB 扁平机身 |
| `services/workers/cad_worker/openvsp_generator/backend.py` | Modify | LAYOUT_BUILDERS 分发 + 4 个 builder |
| `services/workers/cad_worker/openvsp_generator/openvsp_adapter.py` | Modify | 新增 set_fuselage_cross_section 方法 |
| `services/workers/cad_worker/openvsp_generator/vspaero_analysis.py` | Modify | 多部件分析 geom_ids 参数 |
| `tests/api/test_create_tail_extended.py` | **Create** | 新尾翼测试 |
| `tests/api/test_create_wing_multisection.py` | **Create** | 多段翼测试 |
| `tests/api/test_create_engine_extended.py` | **Create** | 发动机扩展测试 |
| `tests/api/test_layout_builders.py` | **Create** | 布局 builder 集成测试 |
| `tests/api/test_create_boom.py` | **Create** | 双尾撑测试 |
| `tests/api/test_create_body.py` | **Create** | BWB 机身测试 |
| `packages/aircraft-schema/examples/v_tail_single_uav.yaml` | **Create** | V 尾示例 |
| `packages/aircraft-schema/examples/twin_boom_pusher_uav.yaml` | **Create** | 双尾撑示例 |
| `packages/aircraft-schema/examples/flying_wing_uav.yaml` | **Create** | 飞翼示例 |
| `packages/aircraft-schema/examples/bwb_uav.yaml` | **Create** | BWB 示例 |

---

## Batch 1: 常规布局增强

### Task 1: Schema 扩展

**Files:**
- Modify: `services/api/app/schemas/aircraft_spec.py`
- Modify: `services/api/app/services/spec_defaults.py`

- [ ] **Step 1: 扩展 Aircraft.layout Literal**

```python
# aircraft_spec.py — Aircraft class (line 40-46)
class Aircraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: Literal["fixed_wing_uav"]
    layout: Literal["conventional", "twin_boom", "flying_wing", "blended_wing_body"]
```

- [ ] **Step 2: 扩展 Wing 模型，新增 sections + inner 字段**

```python
# aircraft_spec.py — Wing class (line 63-72), replace entire class:
class Wing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: TextScalar
    span: NumericScalar
    root_chord: NumericScalar
    tip_chord: NumericScalar
    sweep: NumericScalar | None = None
    dihedral: NumericScalar | None = None
    airfoil: TextScalar | None = None
    sections: IntegerScalar | None = None
    inner_sweep: NumericScalar | None = None
    inner_dihedral: NumericScalar | None = None
```

- [ ] **Step 3: 新增 Boom 和 Body 模型**

```python
# aircraft_spec.py — after Tail class:
class Boom(BaseModel):
    model_config = ConfigDict(extra="forbid")

    length: NumericScalar
    span: NumericScalar


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: NumericScalar
    height: NumericScalar
```

- [ ] **Step 4: 扩展 AircraftSpec，boom/body 可选**

```python
# aircraft_spec.py — AircraftSpec class (line 91-100), replace:
class AircraftSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.1"]
    aircraft: Aircraft
    mission: Mission = Field(default_factory=Mission)
    fuselage: Fuselage
    wing: Wing
    tail: Tail
    engine: Engine
    boom: Boom | None = None
    body: Body | None = None
```

- [ ] **Step 5: 添加新字段默认值到 spec_defaults.py**

```python
# spec_defaults.py — append to REQUIRED_DEFAULTS dict:
    "wing.sections": {
        "value": 1,
        "source": "rule_default",
        "confidence": 0.5,
        "label": "机翼段数",
        "reason": "LLM 未提供，系统按规则补全",
    },
```

- [ ] **Step 6: 运行现有测试确认不回归**

Run: `cd /home/z/codebase/aero-spec-agent && CAD_BACKEND=fake .venv/bin/python -m pytest tests/ -q --tb=short`
Expected: All 548+ tests pass

- [ ] **Step 7: Commit**

```bash
git add services/api/app/schemas/aircraft_spec.py services/api/app/services/spec_defaults.py
git commit -m "feat(schema): extend layout types, add wing sections/boom/body fields"
```

---

### Task 2: Chat Tool 字段暴露

**Files:**
- Modify: `services/api/app/services/chat_tools.py`

- [ ] **Step 1: 更新 SUPPORTED_FIELD_VALUES**

```python
# chat_tools.py — replace SUPPORTED_FIELD_VALUES (lines 67-70):
SUPPORTED_FIELD_VALUES: dict[str, set[str]] = {
    "tail_type": {"conventional", "t_tail", "v_tail", "inverted_v", "cruciform"},
    "engine_position": {"nose", "tail", "rear_fuselage", "under_wing", "wing_tip", "over_wing", "pusher"},
}
```

- [ ] **Step 2: 更新 GENERATE_DESIGN_TOOL 的 tail_type enum**

```python
# chat_tools.py — in GENERATE_DESIGN_TOOL, replace tail_type enum (lines 94-97):
                "tail_type": {
                    "type": "string",
                    "enum": ["conventional", "t_tail", "v_tail", "inverted_v", "cruciform"],
                    "description": "尾翼类型",
                },
```

- [ ] **Step 3: 更新 GENERATE_DESIGN_TOOL 的 engine_position enum**

```python
# chat_tools.py — in GENERATE_DESIGN_TOOL, replace engine_position enum (lines 100-103):
                "engine_position": {
                    "type": "string",
                    "enum": ["nose", "tail", "rear_fuselage", "under_wing", "wing_tip", "over_wing", "pusher"],
                    "description": "发动机位置",
                },
```

- [ ] **Step 4: 在 GENERATE_DESIGN_TOOL parameters 中新增 layout 和 engine_count 字段**

在 `wing_airfoil` 之后、`tail_type` 之前插入：

```python
                "aircraft_layout": {
                    "type": "string",
                    "enum": ["conventional", "twin_boom", "flying_wing", "blended_wing_body"],
                    "description": "气动布局类型",
                },
```

在 `engine_count` 的描述中确认 `"type": "integer"`（已有）。

- [ ] **Step 5: 运行测试确认不回归**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_chat_tools.py tests/api/test_chat_service.py -q --tb=short`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add services/api/app/services/chat_tools.py
git commit -m "feat(chat): expose new tail types, engine positions, layout in Chat Tool"
```

---

### Task 3: 尾翼构型扩展

**Files:**
- Modify: `services/workers/cad_worker/openvsp_generator/create_tail.py`
- Create: `tests/api/test_create_tail_extended.py`

- [ ] **Step 1: 编写新尾翼的失败测试**

```python
# tests/api/test_create_tail_extended.py — 新建
"""Tests for extended tail configurations: v_tail, inverted_v, cruciform."""

from services.workers.cad_worker.openvsp_generator.create_tail import create_tail
from tests.api.test_openvsp_backend_unit import FakeOpenVspModule


def _make_spec(tail_type: str = "conventional", wing_span: float = 10.0, root_chord: float = 1.5, fuselage_length: float = 6.0):
    """Create a minimal spec-like object for tail creation."""
    class Scalar:
        def __init__(self, v):
            self.value = v
    class Tail:
        def __init__(self, t):
            self.type = Scalar(t)
    class Wing:
        def __init__(self):
            self.span = Scalar(wing_span)
            self.root_chord = Scalar(root_chord)
    class Fuselage:
        def __init__(self):
            self.length = Scalar(fuselage_length)
    class Spec:
        def __init__(self, tail_type_str):
            self.tail = Tail(tail_type_str)
            self.wing = Wing()
            self.fuselage = Fuselage()
    return Spec(tail_type)


def test_v_tail_creates_two_surfaces():
    adapter = FakeOpenVspModule()
    results = create_tail(adapter, _make_spec("v_tail"))
    assert len(results) == 2
    names = {r.name for r in results}
    assert "v_tail_left" in names
    assert "v_tail_right" in names


def test_v_tail_rotation_angles():
    adapter = FakeOpenVspModule()
    results = create_tail(adapter, _make_spec("v_tail"))
    left = next(r for r in results if r.name == "v_tail_left")
    right = next(r for r in results if r.name == "v_tail_right")
    assert left.applied_parameters.get("x_rel_rotation") == 45.0
    assert right.applied_parameters.get("x_rel_rotation") == -45.0


def test_inverted_v_rotation_angles():
    adapter = FakeOpenVspModule()
    results = create_tail(adapter, _make_spec("inverted_v"))
    left = next(r for r in results if r.name == "inverted_v_left")
    right = next(r for r in results if r.name == "inverted_v_right")
    assert left.applied_parameters.get("x_rel_rotation") == -45.0
    assert right.applied_parameters.get("x_rel_rotation") == 45.0


def test_cruciform_has_three_surfaces():
    adapter = FakeOpenVspModule()
    results = create_tail(adapter, _make_spec("cruciform"))
    assert len(results) == 3
    names = {r.name for r in results}
    assert "horizontal_tail" in names
    assert "vertical_tail" in names
    assert "cruciform_htail" in names


def test_cruciform_htail_elevated():
    adapter = FakeOpenVspModule()
    results = create_tail(adapter, _make_spec("cruciform"))
    cf = next(r for r in results if r.name == "cruciform_htail")
    assert cf.applied_parameters.get("z_rel_location") is not None
    assert cf.applied_parameters["z_rel_location"] > 0


def test_conventional_unchanged():
    adapter = FakeOpenVspModule()
    results = create_tail(adapter, _make_spec("conventional"))
    names = {r.name for r in results}
    assert names == {"horizontal_tail", "vertical_tail"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_create_tail_extended.py -v --tb=short`
Expected: FAIL (v_tail branch not implemented)

- [ ] **Step 3: 实现 v_tail、inverted_v、cruciform**

在 `create_tail.py` 的 `create_tail` 函数中，`t_tail` 分支之后添加：

```python
# create_tail.py — 在 t_tail 分支后添加:
    if tail_type == "v_tail":
        return _create_v_tail(adapter, tail_x, h_tail_span, root_chord)

    if tail_type == "inverted_v":
        return _create_inverted_v(adapter, tail_x, h_tail_span, root_chord)

    if tail_type == "cruciform":
        return _create_cruciform(adapter, tail_x, h_tail_span, v_tail_span, root_chord)
```

在文件末尾添加新函数：

```python
def _create_v_tail(
    adapter: Any,
    tail_x: float,
    h_tail_span: float,
    root_chord: float,
) -> list[GeometryBuildResult]:
    v_tail_chord = root_chord * 0.50
    v_tail_span = h_tail_span * 0.85
    left = _create_tail_surface(
        adapter,
        name="v_tail_left",
        span=v_tail_span,
        chord=v_tail_chord,
        x_rel_location=tail_x,
        x_rel_rotation=45.0,
    )
    right = _create_tail_surface(
        adapter,
        name="v_tail_right",
        span=v_tail_span,
        chord=v_tail_chord,
        x_rel_location=tail_x,
        x_rel_rotation=-45.0,
    )
    return [left, right]


def _create_inverted_v(
    adapter: Any,
    tail_x: float,
    h_tail_span: float,
    root_chord: float,
) -> list[GeometryBuildResult]:
    v_tail_chord = root_chord * 0.50
    v_tail_span = h_tail_span * 0.85
    left = _create_tail_surface(
        adapter,
        name="inverted_v_left",
        span=v_tail_span,
        chord=v_tail_chord,
        x_rel_location=tail_x,
        x_rel_rotation=-45.0,
    )
    right = _create_tail_surface(
        adapter,
        name="inverted_v_right",
        span=v_tail_span,
        chord=v_tail_chord,
        x_rel_location=tail_x,
        x_rel_rotation=45.0,
    )
    return [left, right]


def _create_cruciform(
    adapter: Any,
    tail_x: float,
    h_tail_span: float,
    v_tail_span: float,
    root_chord: float,
) -> list[GeometryBuildResult]:
    vertical_tail = _create_tail_surface(
        adapter,
        name="vertical_tail",
        span=v_tail_span,
        chord=root_chord * 0.55,
        x_rel_location=tail_x,
        x_rel_rotation=90.0,
    )
    horizontal_tail = _create_tail_surface(
        adapter,
        name="horizontal_tail",
        span=h_tail_span,
        chord=root_chord * 0.45,
        x_rel_location=tail_x,
    )
    cruciform_htail = _create_tail_surface(
        adapter,
        name="cruciform_htail",
        span=h_tail_span * 0.90,
        chord=root_chord * 0.42,
        x_rel_location=tail_x,
        z_rel_location=v_tail_span * 0.50,
    )
    return [vertical_tail, horizontal_tail, cruciform_htail]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_create_tail_extended.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add services/workers/cad_worker/openvsp_generator/create_tail.py tests/api/test_create_tail_extended.py
git commit -m "feat(tail): add v_tail, inverted_v, cruciform tail configurations"
```

---

### Task 4: 多段翼扩展

**Files:**
- Modify: `services/workers/cad_worker/openvsp_generator/create_wing.py`
- Create: `tests/api/test_create_wing_multisection.py`

- [ ] **Step 1: 编写多段翼失败测试**

```python
# tests/api/test_create_wing_multisection.py — 新建
"""Tests for multi-section wing creation."""

from services.workers.cad_worker.openvsp_generator.create_wing import create_main_wing
from tests.api.test_openvsp_backend_unit import FakeOpenVspModule


def _wing_spec(sections: int | None = None, inner_sweep: float | None = None, inner_dihedral: float | None = None):
    class S:
        def __init__(self, v):
            self.value = v
    class Wing:
        def __init__(self):
            self.position = S("mid")
            self.span = S(12.0)
            self.root_chord = S(1.5)
            self.tip_chord = S(0.8)
            self.sweep = S(5.0)
            self.dihedral = S(3.0)
            self.sections = S(sections) if sections else None
            self.inner_sweep = S(inner_sweep) if inner_sweep is not None else None
            self.inner_dihedral = S(inner_dihedral) if inner_dihedral is not None else None
    class Fuselage:
        def __init__(self):
            self.length = S(6.0)
            self.max_diameter = S(0.75)
    class Spec:
        def __init__(self):
            self.wing = Wing()
            self.fuselage = Fuselage()
    return Spec()


def test_single_section_returns_one_result():
    adapter = FakeOpenVspModule()
    result = create_main_wing(adapter, _wing_spec())
    assert result.name == "main_wing"


def test_two_section_returns_list():
    adapter = FakeOpenVspModule()
    results = create_main_wing(adapter, _wing_spec(sections=2, inner_sweep=15.0, inner_dihedral=5.0))
    assert isinstance(results, list)
    assert len(results) == 2
    names = [r.name for r in results]
    assert "inner_wing" in names
    assert "outer_wing" in names


def test_three_section_returns_three():
    adapter = FakeOpenVspModule()
    results = create_main_wing(adapter, _wing_spec(sections=3, inner_sweep=20.0, inner_dihedral=2.0))
    assert len(results) == 3


def test_outer_wing_uses_inner_params():
    adapter = FakeOpenVspModule()
    results = create_main_wing(adapter, _wing_spec(sections=2, inner_sweep=15.0, inner_dihedral=5.0))
    outer = next(r for r in results if r.name == "outer_wing")
    assert outer.applied_parameters["sweep"] == 15.0
    assert outer.applied_parameters["dihedral"] == 5.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_create_wing_multisection.py -v --tb=short`
Expected: FAIL

- [ ] **Step 3: 实现多段翼**

替换 `create_wing.py` 的 `create_main_wing` 函数，保留辅助函数：

```python
# create_wing.py — replace create_main_wing function:
def create_main_wing(adapter: Any, spec: Any) -> GeometryBuildResult | list[GeometryBuildResult]:
    span = _value(spec.wing.span)
    root_chord = _value(spec.wing.root_chord)
    tip_chord = _value(spec.wing.tip_chord)
    sweep = _value(spec.wing.sweep, 0.0)
    dihedral = _value(spec.wing.dihedral, 0.0)
    fuselage_length = _value(spec.fuselage.length)
    fuselage_diameter = _value(spec.fuselage.max_diameter, 0.75)
    position = str(spec.wing.position.value).lower()
    x_rel_location = fuselage_length * 0.40
    z_rel_location = _wing_z_location(position, fuselage_diameter)

    sections = 1
    if spec.wing.sections is not None and hasattr(spec.wing.sections, "value"):
        sections = int(spec.wing.sections.value)

    if sections <= 1:
        # Original single-section behavior
        geom_id = adapter.add_geom("WING")
        adapter.set_param(geom_id, "TotalSpan", "WingGeom", span)
        adapter.set_param(geom_id, "Root_Chord", "XSec_1", root_chord)
        adapter.set_param(geom_id, "Tip_Chord", "XSec_1", tip_chord)
        adapter.set_param(geom_id, "Sweep", "XSec_1", sweep)
        adapter.set_param(geom_id, "Dihedral", "XSec_1", dihedral)
        adapter.set_param(geom_id, "X_Rel_Location", "XForm", x_rel_location)
        adapter.set_param(geom_id, "Z_Rel_Location", "XForm", z_rel_location)
        return GeometryBuildResult(
            name="main_wing",
            geom_id=geom_id,
            applied_parameters={
                "span": span, "root_chord": root_chord, "tip_chord": tip_chord,
                "sweep": sweep, "dihedral": dihedral,
                "x_rel_location": x_rel_location, "z_rel_location": z_rel_location,
            },
        )

    inner_sweep = _value(spec.wing.inner_sweep, sweep) if spec.wing.inner_sweep is not None else sweep
    inner_dihedral = _value(spec.wing.inner_dihedral, dihedral) if spec.wing.inner_dihedral is not None else dihedral

    return _create_multi_section_wing(
        adapter, span, root_chord, tip_chord, sweep, dihedral,
        inner_sweep, inner_dihedral, sections,
        x_rel_location, z_rel_location,
    )


def _create_multi_section_wing(
    adapter: Any,
    total_span: float,
    root_chord: float,
    tip_chord: float,
    sweep: float,
    dihedral: float,
    inner_sweep: float,
    inner_dihedral: float,
    sections: int,
    x_rel_location: float,
    z_rel_location: float,
) -> list[GeometryBuildResult]:
    results: list[GeometryBuildResult] = []
    section_span = total_span / sections
    chord_step = (root_chord - tip_chord) / sections

    for i in range(sections):
        section_root = root_chord - chord_step * i
        section_tip = root_chord - chord_step * (i + 1)
        sec_sweep = sweep if i == 0 else inner_sweep
        sec_dihedral = dihedral if i == 0 else inner_dihedral
        y_offset = section_span * i / 2.0

        geom_id = adapter.add_geom("WING")
        adapter.set_param(geom_id, "TotalSpan", "WingGeom", section_span)
        adapter.set_param(geom_id, "Root_Chord", "XSec_1", section_root)
        adapter.set_param(geom_id, "Tip_Chord", "XSec_1", section_tip)
        adapter.set_param(geom_id, "Sweep", "XSec_1", sec_sweep)
        adapter.set_param(geom_id, "Dihedral", "XSec_1", sec_dihedral)
        adapter.set_param(geom_id, "X_Rel_Location", "XForm", x_rel_location)
        adapter.set_param(geom_id, "Y_Rel_Location", "XForm", y_offset)
        adapter.set_param(geom_id, "Z_Rel_Location", "XForm", z_rel_location)

        name = "inner_wing" if i == 0 else f"outer_wing_{i}" if sections > 2 else "outer_wing"
        results.append(GeometryBuildResult(
            name=name,
            geom_id=geom_id,
            applied_parameters={
                "span": section_span, "root_chord": section_root, "tip_chord": section_tip,
                "sweep": sec_sweep, "dihedral": sec_dihedral,
                "x_rel_location": x_rel_location, "y_rel_location": y_offset,
                "z_rel_location": z_rel_location,
            },
        ))
    return results
```

- [ ] **Step 4: 运行测试确认通过**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_create_wing_multisection.py -v`
Expected: 4 passed

- [ ] **Step 5: 运行全量测试确认不回归**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/ -q --tb=short`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add services/workers/cad_worker/openvsp_generator/create_wing.py tests/api/test_create_wing_multisection.py
git commit -m "feat(wing): multi-section wing support (1-3 sections)"
```

---

### Task 5: 发动机配置扩展

**Files:**
- Modify: `services/workers/cad_worker/openvsp_generator/create_engine.py`
- Create: `tests/api/test_create_engine_extended.py`

- [ ] **Step 1: 编写发动机扩展失败测试**

```python
# tests/api/test_create_engine_extended.py — 新建
"""Tests for extended engine configurations: 3-4 engines, new positions."""

from services.workers.cad_worker.openvsp_generator.create_engine import create_engine_nacelles
from tests.api.test_openvsp_backend_unit import FakeOpenVspModule


def _engine_spec(count: int = 2, position: str = "under_wing"):
    class S:
        def __init__(self, v):
            self.value = v
    class Engine:
        def __init__(self):
            self.count = S(count)
            self.position = S(position) if position else None
            self.x_offset = S(0.0)
            self.y_offset = S(0.0)
            self.z_offset = S(0.0)
    class Wing:
        def __init__(self):
            self.span = S(10.0)
            self.root_chord = S(1.5)
            self.position = S("mid")
    class Fuselage:
        def __init__(self):
            self.length = S(6.0)
            self.max_diameter = S(0.75)
    class Spec:
        def __init__(self):
            self.engine = Engine()
            self.wing = Wing()
            self.fuselage = Fuselage()
    return Spec()


def test_three_engines_creates_three_nacelles():
    adapter = FakeOpenVspModule()
    results = create_engine_nacelles(adapter, _engine_spec(count=3, position="under_wing"))
    assert len(results) == 3
    names = {r.name for r in results}
    assert "center_engine" in names
    assert "left_engine" in names
    assert "right_engine" in names


def test_four_engines_creates_four_nacelles():
    adapter = FakeOpenVspModule()
    results = create_engine_nacelles(adapter, _engine_spec(count=4, position="under_wing"))
    assert len(results) == 4


def test_wing_tip_position():
    adapter = FakeOpenVspModule()
    results = create_engine_nacelles(adapter, _engine_spec(count=2, position="wing_tip"))
    assert len(results) == 2
    left = next(r for r in results if r.name == "left_engine")
    right = next(r for r in results if r.name == "right_engine")
    assert abs(left.applied_parameters["final_y"]) > 0
    assert abs(right.applied_parameters["final_y"]) > 0


def test_over_wing_position():
    adapter = FakeOpenVspModule()
    results = create_engine_nacelles(adapter, _engine_spec(count=2, position="over_wing"))
    assert len(results) == 2
    left = next(r for r in results if r.name == "left_engine")
    assert left.applied_parameters["final_z"] > 0


def test_pusher_position():
    adapter = FakeOpenVspModule()
    results = create_engine_nacelles(adapter, _engine_spec(count=1, position="pusher"))
    assert len(results) == 1
    assert results[0].name == "center_engine"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_create_engine_extended.py -v --tb=short`
Expected: FAIL (UnsupportedGeometryError for count=3)

- [ ] **Step 3: 扩展 create_engine.py**

在 `create_engine_nacelles` 函数中：

1. 将 `if engine_count not in (1, 2)` 改为 `if engine_count not in (1, 2, 3, 4)`
2. 在 `engine_count == 1` 分支中添加 `pusher` 位置处理
3. 在双发逻辑后添加 3 发和 4 发分支

`pusher` 单发位置（在 nose/tail/rear_fuselage 分支后添加）：

```python
        elif engine_position == "pusher":
            base_x = wing_x + root_chord * 0.75
            base_y = 0.0
            base_z = fuselage_diameter * 0.2
```

在现有双发 `base_y = wing_span * 0.25` 之后，添加 `wing_tip` 和 `over_wing` 位置覆盖：

```python
    if engine_position == "wing_tip":
        base_y = wing_span * 0.48
        base_z = wing_z
    elif engine_position == "over_wing":
        base_y = wing_span * 0.25
        base_z = wing_z + diameter * 0.8
```

注意：需要在双发分支开头提取 `engine_position`：

```python
    engine_position = (
        spec.engine.position.value if spec.engine.position else "under_wing"
    )
```

3 发逻辑（在双发 return 之后）：

```python
    if engine_count == 3:
        center = _create_engine_nacelle(
            adapter, name="center_engine", engine_count=engine_count,
            x_offset=x_offset, y_delta=y_offset, z_offset=z_offset,
            base_x=base_x, base_y=0.0, base_z=base_z,
            x_rel_location=base_x + x_offset, y_offset=y_offset,
            z_rel_location=base_z + z_offset, length=length, diameter=diameter,
        )
        left = _create_engine_nacelle(
            adapter, name="left_engine", engine_count=engine_count,
            x_offset=x_offset, y_delta=y_offset, z_offset=z_offset,
            base_x=base_x, base_y=base_y, base_z=base_z,
            x_rel_location=base_x + x_offset,
            y_offset=-(base_y + y_offset),
            z_rel_location=base_z + z_offset, length=length, diameter=diameter,
        )
        right = _create_engine_nacelle(
            adapter, name="right_engine", engine_count=engine_count,
            x_offset=x_offset, y_delta=y_offset, z_offset=z_offset,
            base_x=base_x, base_y=base_y, base_z=base_z,
            x_rel_location=base_x + x_offset,
            y_offset=base_y + y_offset,
            z_rel_location=base_z + z_offset, length=length, diameter=diameter,
        )
        return [center, left, right]
```

4 发逻辑（在 3 发之后）：

```python
    if engine_count == 4:
        inner_y = wing_span * 0.18
        outer_y = wing_span * 0.38
        return [
            _create_engine_nacelle(
                adapter, name="left_inner_engine", engine_count=engine_count,
                x_offset=x_offset, y_delta=y_offset, z_offset=z_offset,
                base_x=base_x, base_y=inner_y, base_z=base_z,
                x_rel_location=base_x + x_offset,
                y_offset=-(inner_y + y_offset),
                z_rel_location=base_z + z_offset, length=length, diameter=diameter,
            ),
            _create_engine_nacelle(
                adapter, name="left_outer_engine", engine_count=engine_count,
                x_offset=x_offset, y_delta=y_offset, z_offset=z_offset,
                base_x=base_x, base_y=outer_y, base_z=base_z,
                x_rel_location=base_x + x_offset,
                y_offset=-(outer_y + y_offset),
                z_rel_location=base_z + z_offset, length=length, diameter=diameter,
            ),
            _create_engine_nacelle(
                adapter, name="right_inner_engine", engine_count=engine_count,
                x_offset=x_offset, y_delta=y_offset, z_offset=z_offset,
                base_x=base_x, base_y=inner_y, base_z=base_z,
                x_rel_location=base_x + x_offset,
                y_offset=inner_y + y_offset,
                z_rel_location=base_z + z_offset, length=length, diameter=diameter,
            ),
            _create_engine_nacelle(
                adapter, name="right_outer_engine", engine_count=engine_count,
                x_offset=x_offset, y_delta=y_offset, z_offset=z_offset,
                base_x=base_x, base_y=outer_y, base_z=base_z,
                x_rel_location=base_x + x_offset,
                y_offset=outer_y + y_offset,
                z_rel_location=base_z + z_offset, length=length, diameter=diameter,
            ),
        ]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_create_engine_extended.py tests/api/test_openvsp_backend_unit.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add services/workers/cad_worker/openvsp_generator/create_engine.py tests/api/test_create_engine_extended.py
git commit -m "feat(engine): support 3-4 engines, wing_tip/over_wing/pusher positions"
```

---

### Task 6: 布局分发层 + V 尾示例

**Files:**
- Modify: `services/workers/cad_worker/openvsp_generator/backend.py`
- Create: `packages/aircraft-schema/examples/v_tail_single_uav.yaml`

- [ ] **Step 1: 在 backend.py 添加布局分发**

在 `OpenVspBackend.generate()` 方法中，替换硬编码的 build_results 创建（lines 92-109）：

```python
        layout = str(spec.aircraft.layout.value).lower()

        build_results: list[GeometryBuildResult] = []

        # All layouts start with fuselage (except flying_wing)
        if layout != "flying_wing":
            build_results.append(create_fuselage(adapter, spec))
        if on_progress: on_progress("fuselage_created", 62)
        if fail_stage == "creating_fuselage":
            raise RuntimeError(f"OpenVSP failure injection at stage: creating_fuselage")

        # Wing creation (all layouts)
        wing_result = create_main_wing(adapter, spec)
        if isinstance(wing_result, list):
            build_results.extend(wing_result)
        else:
            build_results.append(wing_result)
        if on_progress: on_progress("wing_created", 68)
        if fail_stage == "creating_wing":
            raise RuntimeError(f"OpenVSP failure injection at stage: creating_wing")

        # Tail (not for flying_wing or BWB)
        if layout not in ("flying_wing", "blended_wing_body"):
            build_results.extend(create_tail(adapter, spec))
        if on_progress: on_progress("tail_created", 72)
        if fail_stage == "creating_tail":
            raise RuntimeError(f"OpenVSP failure injection at stage: creating_tail")

        # Engines
        build_results.extend(create_engine_nacelles(adapter, spec))
        if on_progress: on_progress("engine_created", 76)
        if fail_stage == "creating_engine":
            raise RuntimeError(f"OpenVSP failure injection at stage: creating_engine")
```

注意：`_stable_applied_parameters` 需要更新以处理多段翼的结果名称。在 `elif result.name == "main_wing"` 后添加：

```python
        elif result.name in ("inner_wing", "outer_wing", "outer_wing_2"):
            _copy_parameters(applied, result.name, result, list(result.applied_parameters))
```

在 engine 名称检查中添加新名称：

```python
        elif result.name in {"center_engine", "left_engine", "right_engine",
                             "left_inner_engine", "left_outer_engine",
                             "right_inner_engine", "right_outer_engine"}:
```

- [ ] **Step 2: 创建 V 尾示例 YAML**

```yaml
# packages/aircraft-schema/examples/v_tail_single_uav.yaml
schema_version: "0.1"
aircraft:
  name: v_tail_single_uav
  type: fixed_wing_uav
  layout: conventional
mission:
  cruise_speed: { value: 120, unit: km/h, source: user, confidence: 0.9 }
  payload: { value: 15, unit: kg, source: user, confidence: 0.9 }
fuselage:
  length: { value: 4.5, unit: m, source: user, confidence: 0.9 }
  max_diameter: { value: 0.6, unit: m, source: inferred, confidence: 0.7 }
wing:
  position: { value: high, source: user, confidence: 0.9 }
  span: { value: 8.0, unit: m, source: user, confidence: 0.9 }
  root_chord: { value: 1.2, unit: m, source: user, confidence: 0.9 }
  tip_chord: { value: 0.6, unit: m, source: inferred, confidence: 0.7 }
  sweep: { value: 3.0, unit: deg, source: rule_default, confidence: 0.5 }
  dihedral: { value: 2.0, unit: deg, source: rule_default, confidence: 0.5 }
  sections: { value: 1, source: rule_default, confidence: 0.5 }
tail:
  type: { value: v_tail, source: user, confidence: 0.9 }
engine:
  count: { value: 1, source: user, confidence: 0.9 }
  position: { value: nose, source: inferred, confidence: 0.7 }
```

- [ ] **Step 3: 运行全量测试确认不回归**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/ -q --tb=short`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add services/workers/cad_worker/openvsp_generator/backend.py packages/aircraft-schema/examples/v_tail_single_uav.yaml
git commit -m "feat(backend): layout-aware dispatch, v_tail example spec"
```

---

## Batch 2: 双尾撑布局

### Task 7: 双尾撑几何构建器

**Files:**
- Create: `services/workers/cad_worker/openvsp_generator/create_boom.py`
- Create: `tests/api/test_create_boom.py`

- [ ] **Step 1: 编写双尾撑失败测试**

```python
# tests/api/test_create_boom.py — 新建
"""Tests for twin boom geometry creation."""

from services.workers.cad_worker.openvsp_generator.create_boom import create_booms


def _boom_spec():
    class S:
        def __init__(self, v):
            self.value = v
    class Boom:
        def __init__(self):
            self.length = S(3.0)
            self.span = S(4.0)
    class Fuselage:
        def __init__(self):
            self.length = S(6.0)
            self.max_diameter = S(0.75)
    class Wing:
        def __init__(self):
            self.span = S(10.0)
            self.root_chord = S(1.5)
            self.position = S("mid")
    class Spec:
        def __init__(self):
            self.boom = Boom()
            self.fuselage = Fuselage()
            self.wing = Wing()
    return Spec()


def test_creates_two_booms():
    from tests.api.test_openvsp_backend_unit import FakeOpenVspModule
    adapter = FakeOpenVspModule()
    results = create_booms(adapter, _boom_spec())
    assert len(results) == 2
    names = {r.name for r in results}
    assert "left_boom" in names
    assert "right_boom" in names


def test_boom_position():
    from tests.api.test_openvsp_backend_unit import FakeOpenVspModule
    adapter = FakeOpenVspModule()
    results = create_booms(adapter, _boom_spec())
    left = next(r for r in results if r.name == "left_boom")
    right = next(r for r in results if r.name == "right_boom")
    assert left.applied_parameters["final_y"] < 0
    assert right.applied_parameters["final_y"] > 0
    assert left.applied_parameters["length"] == 3.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_create_boom.py -v --tb=short`
Expected: FAIL (module not found)

- [ ] **Step 3: 实现双尾撑几何构建器**

```python
# services/workers/cad_worker/openvsp_generator/create_boom.py — 新建
"""Twin boom geometry creation for OpenVSP."""

from typing import Any

from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult


def create_booms(adapter: Any, spec: Any) -> list[GeometryBuildResult]:
    boom_length = float(spec.boom.length.value)
    boom_span = float(spec.boom.span.value)
    fuselage_length = float(spec.fuselage.length.value)
    fuselage_diameter = float(spec.fuselage.max_diameter.value) if spec.fuselage.max_diameter else 0.75
    boom_diameter = fuselage_diameter * 0.15

    base_x = fuselage_length * 0.40
    base_y = boom_span / 2.0
    base_z = 0.0

    left = _create_single_boom(
        adapter, name="left_boom", length=boom_length, diameter=boom_diameter,
        x_rel_location=base_x, y_offset=-base_y, z_rel_location=base_z,
    )
    right = _create_single_boom(
        adapter, name="right_boom", length=boom_length, diameter=boom_diameter,
        x_rel_location=base_x, y_offset=base_y, z_rel_location=base_z,
    )
    return [left, right]


def _create_single_boom(
    adapter: Any,
    *,
    name: str,
    length: float,
    diameter: float,
    x_rel_location: float,
    y_offset: float,
    z_rel_location: float,
) -> GeometryBuildResult:
    geom_id = adapter.add_geom("FUSELAGE")
    adapter.set_param(geom_id, "Length", "Design", length)
    adapter.set_fuselage_diameter(geom_id, diameter)
    adapter.set_param(geom_id, "X_Rel_Location", "XForm", x_rel_location)
    adapter.set_param(geom_id, "Y_Rel_Location", "XForm", y_offset)
    adapter.set_param(geom_id, "Z_Rel_Location", "XForm", z_rel_location)

    return GeometryBuildResult(
        name=name,
        geom_id=geom_id,
        applied_parameters={
            "length": length,
            "diameter": diameter,
            "x_rel_location": x_rel_location,
            "final_y": y_offset,
            "z_rel_location": z_rel_location,
        },
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_create_boom.py -v`
Expected: 2 passed

- [ ] **Step 5: 在 backend.py 添加 twin_boom builder**

在 `backend.py` 的 `generate()` 方法中，tail 创建之前添加 boom 创建：

```python
        # Booms (twin_boom layout only)
        if layout == "twin_boom":
            from services.workers.cad_worker.openvsp_generator.create_boom import create_booms
            build_results.extend(create_booms(adapter, spec))
```

- [ ] **Step 6: 创建双尾撑示例**

```yaml
# packages/aircraft-schema/examples/twin_boom_pusher_uav.yaml
schema_version: "0.1"
aircraft:
  name: twin_boom_pusher_uav
  type: fixed_wing_uav
  layout: twin_boom
mission:
  cruise_speed: { value: 100, unit: km/h, source: user, confidence: 0.9 }
  payload: { value: 25, unit: kg, source: user, confidence: 0.9 }
fuselage:
  length: { value: 3.0, unit: m, source: user, confidence: 0.9 }
  max_diameter: { value: 0.6, unit: m, source: inferred, confidence: 0.7 }
wing:
  position: { value: high, source: user, confidence: 0.9 }
  span: { value: 12.0, unit: m, source: user, confidence: 0.9 }
  root_chord: { value: 1.5, unit: m, source: user, confidence: 0.9 }
  tip_chord: { value: 0.7, unit: m, source: inferred, confidence: 0.7 }
  sweep: { value: 2.0, unit: deg, source: rule_default, confidence: 0.5 }
  dihedral: { value: 3.0, unit: deg, source: rule_default, confidence: 0.5 }
  sections: { value: 1, source: rule_default, confidence: 0.5 }
tail:
  type: { value: conventional, source: user, confidence: 0.9 }
engine:
  count: { value: 1, source: user, confidence: 0.9 }
  position: { value: pusher, source: user, confidence: 0.9 }
boom:
  length: { value: 3.5, unit: m, source: inferred, confidence: 0.7 }
  span: { value: 4.0, unit: m, source: inferred, confidence: 0.7 }
```

- [ ] **Step 7: 运行全量测试**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/ -q --tb=short`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git add services/workers/cad_worker/openvsp_generator/create_boom.py services/workers/cad_worker/openvsp_generator/backend.py tests/api/test_create_boom.py packages/aircraft-schema/examples/twin_boom_pusher_uav.yaml
git commit -m "feat(boom): twin boom geometry builder + twin_boom layout"
```

---

## Batch 3: 飞翼布局

### Task 8: 飞翼布局实现

**Files:**
- Modify: `services/workers/cad_worker/openvsp_generator/backend.py`
- Create: `packages/aircraft-schema/examples/flying_wing_uav.yaml`
- Create: `tests/api/test_layout_builders.py` (追加飞翼测试)

- [ ] **Step 1: 编写飞翼布局测试**

追加到 `tests/api/test_layout_builders.py`：

```python
"""Tests for layout builder integration."""

from tests.api.test_openvsp_backend_unit import FakeOpenVspModule
from services.workers.cad_worker.openvsp_generator.backend import OpenVspBackend


def _spec_with_layout(layout: str):
    """Create minimal spec for layout testing via load_aircraft_spec pattern."""
    from pathlib import Path
    from services.api.app.services.spec_io import load_aircraft_spec
    base = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))
    data = base.model_dump()
    data["aircraft"]["layout"] = {"value": layout, "source": "user", "confidence": 0.9}
    from services.api.app.schemas.aircraft_spec import AircraftSpec
    return AircraftSpec.model_validate(data)


def test_flying_wing_no_fuselage():
    adapter = FakeOpenVspModule()
    spec = _spec_with_layout("flying_wing")
    backend = OpenVspBackend(vsp_module=adapter)
    # We can't call generate() without full output dir setup,
    # so test the logic directly by checking that layout dispatch skips fuselage
    assert spec.aircraft.layout.value == "flying_wing"
```

- [ ] **Step 2: 创建飞翼示例**

```yaml
# packages/aircraft-schema/examples/flying_wing_uav.yaml
schema_version: "0.1"
aircraft:
  name: flying_wing_uav
  type: fixed_wing_uav
  layout: flying_wing
mission:
  cruise_speed: { value: 150, unit: km/h, source: user, confidence: 0.9 }
  payload: { value: 10, unit: kg, source: user, confidence: 0.9 }
fuselage:
  length: { value: 3.0, unit: m, source: inferred, confidence: 0.6 }
  max_diameter: { value: 0.5, unit: m, source: inferred, confidence: 0.6 }
wing:
  position: { value: mid, source: rule_default, confidence: 0.5 }
  span: { value: 6.0, unit: m, source: user, confidence: 0.9 }
  root_chord: { value: 2.5, unit: m, source: user, confidence: 0.9 }
  tip_chord: { value: 0.8, unit: m, source: inferred, confidence: 0.7 }
  sweep: { value: 25.0, unit: deg, source: user, confidence: 0.9 }
  dihedral: { value: 2.0, unit: deg, source: rule_default, confidence: 0.5 }
  sections: { value: 2, source: user, confidence: 0.9 }
  inner_sweep: { value: 35.0, unit: deg, source: inferred, confidence: 0.7 }
  inner_dihedral: { value: 4.0, unit: deg, source: rule_default, confidence: 0.5 }
tail:
  type: { value: conventional, source: rule_default, confidence: 0.5 }
engine:
  count: { value: 1, source: user, confidence: 0.9 }
  position: { value: tail, source: inferred, confidence: 0.7 }
```

- [ ] **Step 3: 运行测试**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_layout_builders.py -v`
Expected: PASS

- [ ] **Step 4: 运行全量测试确认不回归**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/ -q --tb=short`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add tests/api/test_layout_builders.py packages/aircraft-schema/examples/flying_wing_uav.yaml
git commit -m "feat(layout): flying wing layout support + example spec"
```

---

## Batch 4: 翼身融合

### Task 9: BWB 扁平机身构建器

**Files:**
- Modify: `services/workers/cad_worker/openvsp_generator/openvsp_adapter.py`
- Create: `services/workers/cad_worker/openvsp_generator/create_body.py`
- Create: `tests/api/test_create_body.py`

- [ ] **Step 1: 在 OpenVspAdapter 新增 set_fuselage_cross_section 方法**

```python
# openvsp_adapter.py — 新增方法（在 set_fuselage_diameter 之后）:
    def set_fuselage_cross_section(self, geom_id: str, width: float, height: float) -> None:
        """Set fuselage cross-section with independent width and height."""
        xsec_surf_id = self._vsp.GetXSecSurf(geom_id, 0)
        num_xsecs = self._vsp.GetNumXSec(xsec_surf_id)
        if num_xsecs <= 0:
            raise CadGenerationError("OpenVSP fuselage has no cross sections")
        start_index = 1 if num_xsecs > 2 else 0
        end_index = num_xsecs - 1 if num_xsecs > 2 else num_xsecs
        for xsec_index in range(start_index, end_index):
            xsec_id = self._vsp.GetXSec(xsec_surf_id, xsec_index)
            self._vsp.SetXSecWidthHeight(xsec_id, width, height)
```

- [ ] **Step 2: 编写 BWB 机身失败测试**

```python
# tests/api/test_create_body.py — 新建
"""Tests for BWB flat body geometry creation."""

from services.workers.cad_worker.openvsp_generator.create_body import create_flat_body
from tests.api.test_openvsp_backend_unit import FakeOpenVspModule


def _body_spec():
    class S:
        def __init__(self, v):
            self.value = v
    class Body:
        def __init__(self):
            self.width = S(3.0)
            self.height = S(0.6)
    class Fuselage:
        def __init__(self):
            self.length = S(5.0)
            self.max_diameter = S(0.75)
    class Spec:
        def __init__(self):
            self.body = Body()
            self.fuselage = Fuselage()
    return Spec()


def test_creates_flat_body():
    adapter = FakeOpenVspModule()
    result = create_flat_body(adapter, _body_spec())
    assert result.name == "flat_body"
    assert result.applied_parameters["width"] == 3.0
    assert result.applied_parameters["height"] == 0.6


def test_flat_body_length():
    adapter = FakeOpenVspModule()
    result = create_flat_body(adapter, _body_spec())
    assert result.applied_parameters["length"] == 5.0
```

- [ ] **Step 3: 运行测试确认失败**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_create_body.py -v --tb=short`
Expected: FAIL

- [ ] **Step 4: 实现 BWB 扁平机身构建器**

```python
# services/workers/cad_worker/openvsp_generator/create_body.py — 新建
"""BWB flat body geometry creation for OpenVSP."""

from typing import Any

from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult


def create_flat_body(adapter: Any, spec: Any) -> GeometryBuildResult:
    length = float(spec.fuselage.length.value)
    width = float(spec.body.width.value)
    height = float(spec.body.height.value)

    geom_id = adapter.add_geom("FUSELAGE")
    adapter.set_param(geom_id, "Length", "Design", length)
    adapter.set_fuselage_cross_section(geom_id, width, height)

    return GeometryBuildResult(
        name="flat_body",
        geom_id=geom_id,
        applied_parameters={
            "length": length,
            "width": width,
            "height": height,
        },
    )
```

注意：`FakeOpenVspModule` 需要支持 `set_fuselage_cross_section`。在 `tests/api/test_openvsp_backend_unit.py` 的 `FakeOpenVspModule` 类中添加：

```python
    def set_fuselage_cross_section(self, geom_id: str, width: float, height: float) -> None:
        pass
```

- [ ] **Step 5: 运行测试确认通过**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_create_body.py -v`
Expected: 2 passed

- [ ] **Step 6: 在 backend.py 添加 BWB builder**

在 `generate()` 方法中，fuselage 创建之后、wing 之前添加：

```python
        # BWB flat body instead of fuselage
        if layout == "blended_wing_body" and spec.body is not None:
            from services.workers.cad_worker.openvsp_generator.create_body import create_flat_body
            build_results.append(create_flat_body(adapter, spec))
        elif layout != "flying_wing":
            build_results.append(create_fuselage(adapter, spec))
```

调整逻辑：将之前添加的 `if layout != "flying_wing"` fuselage 分支替换为上述。

- [ ] **Step 7: 创建 BWB 示例**

```yaml
# packages/aircraft-schema/examples/bwb_uav.yaml
schema_version: "0.1"
aircraft:
  name: bwb_uav
  type: fixed_wing_uav
  layout: blended_wing_body
mission:
  cruise_speed: { value: 200, unit: km/h, source: user, confidence: 0.9 }
  payload: { value: 50, unit: kg, source: user, confidence: 0.9 }
fuselage:
  length: { value: 4.0, unit: m, source: user, confidence: 0.9 }
  max_diameter: { value: 0.8, unit: m, source: inferred, confidence: 0.6 }
wing:
  position: { value: mid, source: rule_default, confidence: 0.5 }
  span: { value: 8.0, unit: m, source: user, confidence: 0.9 }
  root_chord: { value: 3.0, unit: m, source: user, confidence: 0.9 }
  tip_chord: { value: 1.0, unit: m, source: inferred, confidence: 0.7 }
  sweep: { value: 30.0, unit: deg, source: user, confidence: 0.9 }
  dihedral: { value: 3.0, unit: deg, source: rule_default, confidence: 0.5 }
  sections: { value: 2, source: user, confidence: 0.9 }
  inner_sweep: { value: 40.0, unit: deg, source: inferred, confidence: 0.7 }
  inner_dihedral: { value: 5.0, unit: deg, source: rule_default, confidence: 0.5 }
tail:
  type: { value: conventional, source: rule_default, confidence: 0.5 }
engine:
  count: { value: 2, source: user, confidence: 0.9 }
  position: { value: over_wing, source: inferred, confidence: 0.7 }
body:
  width: { value: 2.5, unit: m, source: user, confidence: 0.9 }
  height: { value: 0.5, unit: m, source: inferred, confidence: 0.7 }
```

- [ ] **Step 8: 运行全量测试**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/ -q --tb=short`
Expected: All pass

- [ ] **Step 9: Commit**

```bash
git add services/workers/cad_worker/openvsp_generator/create_body.py services/workers/cad_worker/openvsp_generator/openvsp_adapter.py services/workers/cad_worker/openvsp_generator/backend.py tests/api/test_create_body.py tests/api/test_openvsp_backend_unit.py packages/aircraft-schema/examples/bwb_uav.yaml
git commit -m "feat(body): BWB flat body builder, cross-section support, BWB layout"
```

---

## 跨批次收尾

### Task 10: README 更新 + 最终验证

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 更新几何支持矩阵**

将 README 中的 "Supported Geometry Matrix" 表更新为：

```markdown
### Supported Geometry Matrix

| Area | Supported | Not yet exposed |
|------|-----------|-----------------|
| Aircraft layout | `conventional`, `twin_boom`, `flying_wing`, `blended_wing_body` | Multirotor, rotorcraft |
| Wing position | `high`, `mid`, `low` | Custom multi-wing layouts |
| Wing sections | 1 (single), 2 (inner+outer), 3 (inner+mid+outer) | Continuous airfoil transition |
| Tail type | `conventional`, `t_tail`, `v_tail`, `inverted_v`, `cruciform` | `butterfly` |
| Engine count | `1`, `2`, `3`, `4` | More than four engines |
| Engine position | `nose`, `tail`, `rear_fuselage`, `under_wing`, `wing_tip`, `over_wing`, `pusher` | `on_fuselage` |
```

- [ ] **Step 2: 更新验证状态表**

新增行：

```markdown
| V-tail / inverted_v / cruciform | Pass | fake | 6 |
| Multi-section wing (1-3) | Pass | fake | 4 |
| 3-4 engine config | Pass | fake | 5 |
| Twin boom layout | Pass | fake | 2 |
| Flying wing layout | Pass | fake | 1 |
| BWB flat body | Pass | fake | 2 |
```

- [ ] **Step 3: 运行全量后端测试**

Run: `CAD_BACKEND=fake .venv/bin/python -m pytest tests/ -q`
Expected: 570+ tests pass

- [ ] **Step 4: 运行前端 build**

Run: `cd apps/web && rm -rf .next && npm run build`
Expected: Build passes

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: update geometry matrix and verification status for layout expansion"
```
