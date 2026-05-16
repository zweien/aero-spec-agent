# Part Selection Modification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `modify_selected_part` tool so that clicking any aircraft part (fuselage, wing, tail, engine) in the 3D viewer enables natural-language parameter modification via chat.

**Architecture:** Single `modify_selected_part` tool with expanded `operation` enum. Backend routes operations by `part_ref` to spec patch logic. Engine `move_*` operations keep existing incremental offset behavior; new `set_*` operations use absolute values. Frontend only needs label and display updates.

**Tech Stack:** Python/FastAPI backend, React/Next.js/TypeScript frontend, pytest for backend tests.

---

### Task 1: Update tool schema and add operation routing map

**Files:**
- Modify: `services/api/app/services/chat_service.py:240-293`

- [ ] **Step 1: Replace `MODIFY_SELECTED_PART_TOOL` schema**

In `services/api/app/services/chat_service.py`, replace the entire `MODIFY_SELECTED_PART_TOOL` dict (lines 240-287) with:

```python
MODIFY_SELECTED_PART_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "modify_selected_part",
        "description": (
            "修改选中的飞机部件参数。根据当前 selected_refs 确定部件类型。\n"
            "支持的操作：\n"
            "- 机身(part:fuselage): set_length(设置长度/m), set_diameter(设置直径/m)\n"
            "- 机翼(part:main_wing): set_span(设置翼展/m), set_root_chord(设置翼根弦长/m), "
            "set_tip_chord(设置翼尖弦长/m), set_sweep(设置后掠角/deg), set_dihedral(设置上反角/deg)\n"
            "- 尾翼(part:tail): set_tail_type(设置尾翼类型)\n"
            "- 发动机(part:left_engine/part:right_engine): move_outboard/inboard/forward/backward/up/down(移动/m，增量)\n"
            "set_* 操作 value 为目标绝对值；move_* 操作 value 为移动距离增量。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "part_ref": {
                    "type": "string",
                    "enum": [
                        "part:left_engine",
                        "part:right_engine",
                        "part:fuselage",
                        "part:main_wing",
                        "part:tail",
                    ],
                    "description": "要修改的部件引用，通常来自当前 selected_refs",
                },
                "operation": {
                    "type": "string",
                    "enum": [
                        "set_length",
                        "set_diameter",
                        "set_span",
                        "set_root_chord",
                        "set_tip_chord",
                        "set_sweep",
                        "set_dihedral",
                        "set_tail_type",
                        "move_outboard",
                        "move_inboard",
                        "move_forward",
                        "move_backward",
                        "move_up",
                        "move_down",
                    ],
                    "description": "操作类型。set_* 用绝对值，move_* 用增量。",
                },
                "value": {
                    "description": "set_* 操作为目标绝对值，move_* 操作为移动增量 (m)",
                },
                "reason": {
                    "type": "string",
                    "description": "修改原因",
                },
            },
            "required": ["part_ref", "operation", "value"],
        },
    },
}
```

- [ ] **Step 2: Add `_PART_SET_OPERATIONS` routing map**

Add this class variable to `ChatService`, right before the existing `_ENGINE_MOVE_MAP` (line 686):

```python
    _PART_SET_OPERATIONS: dict[str, dict[str, tuple[str, str]]] = {
        "part:fuselage": {
            "set_length": ("fuselage", "length", "m"),
            "set_diameter": ("fuselage", "max_diameter", "m"),
        },
        "part:main_wing": {
            "set_span": ("wing", "span", "m"),
            "set_root_chord": ("wing", "root_chord", "m"),
            "set_tip_chord": ("wing", "tip_chord", "m"),
            "set_sweep": ("wing", "sweep", "deg"),
            "set_dihedral": ("wing", "dihedral", "deg"),
        },
        "part:tail": {
            "set_tail_type": ("tail", "type", None),
        },
    }
```

Each value is `(section, field_name, default_unit)`. `None` unit means no unit field (text scalars).

- [ ] **Step 3: Run existing tests to verify schema change doesn't break unrelated code**

Run: `cd /home/z/codebase/aero-spec-agent && CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_chat_service.py::test_modify_selected_part_tool_schema -v`

This will FAIL because the test still checks for `delta_m`. That's expected — we fix it in Task 3.

- [ ] **Step 4: Commit**

```bash
git add services/api/app/services/chat_service.py
git commit -m "feat: expand modify_selected_part tool schema and routing map"
```

---

### Task 2: Rewrite `_handle_modify_selected_part` to handle all parts

**Files:**
- Modify: `services/api/app/services/chat_service.py:695-793`

- [ ] **Step 1: Write failing tests for new operations**

In `tests/api/test_chat_service.py`, add these tests after the existing `test_engine_move_map_covers_all_operations`:

```python
from pathlib import Path
import pytest
from services.api.app.services.chat_service import ChatService, _pre_fill_none_scalars
from services.api.app.services.spec_io import load_aircraft_spec
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.version_store import VersionStore


EXAMPLE = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


class FakeJobRunner:
    """Minimal job runner that returns a fake successful job."""
    def __init__(self, tmp_path: Path) -> None:
        self._store = VersionStore(tmp_path)

    def generate(self, design_id: str, spec):
        return self._store.create(design_id, spec, {"aircraft.vsp3": "fake"})


def _service_with_spec(tmp_path: Path) -> tuple[ChatService, None]:
    svc = ChatService(storage_root=tmp_path)
    svc.set_job_runner(FakeJobRunner(tmp_path))
    state = svc.get_or_create_state("test-mod")
    state.current_spec = load_aircraft_spec(EXAMPLE)
    return svc


@pytest.mark.anyio
async def test_handle_modify_selected_part_set_fuselage_length(tmp_path):
    svc = _service_with_spec(tmp_path)
    state = svc.get_or_create_state("test-mod")
    events = [
        e async for e in svc._handle_modify_selected_part(
            state,
            {"part_ref": "part:fuselage", "operation": "set_length", "value": 8.5},
            "tc-1",
        )
    ]
    assert any("generation_complete" in e for e in events)
    assert state.current_spec is not None
    assert state.current_spec.fuselage.length.value == 8.5
    assert state.current_spec.fuselage.length.source == "user"
    assert state.current_spec.fuselage.length.confidence == 1.0


@pytest.mark.anyio
async def test_handle_modify_selected_part_set_fuselage_diameter(tmp_path):
    svc = _service_with_spec(tmp_path)
    state = svc.get_or_create_state("test-mod")
    events = [
        e async for e in svc._handle_modify_selected_part(
            state,
            {"part_ref": "part:fuselage", "operation": "set_diameter", "value": 1.2},
            "tc-2",
        )
    ]
    assert any("generation_complete" in e for e in events)
    assert state.current_spec is not None
    assert state.current_spec.fuselage.max_diameter is not None
    assert state.current_spec.fuselage.max_diameter.value == 1.2


@pytest.mark.anyio
async def test_handle_modify_selected_part_set_wing_span(tmp_path):
    svc = _service_with_spec(tmp_path)
    state = svc.get_or_create_state("test-mod")
    events = [
        e async for e in svc._handle_modify_selected_part(
            state,
            {"part_ref": "part:main_wing", "operation": "set_span", "value": 14.0},
            "tc-3",
        )
    ]
    assert any("generation_complete" in e for e in events)
    assert state.current_spec is not None
    assert state.current_spec.wing.span.value == 14.0


@pytest.mark.anyio
async def test_handle_modify_selected_part_set_sweep_prefills_none(tmp_path):
    svc = _service_with_spec(tmp_path)
    state = svc.get_or_create_state("test-mod")
    # The example spec may have sweep=None; verify we handle it
    events = [
        e async for e in svc._handle_modify_selected_part(
            state,
            {"part_ref": "part:main_wing", "operation": "set_sweep", "value": 5.0},
            "tc-4",
        )
    ]
    assert any("generation_complete" in e for e in events)
    assert state.current_spec is not None
    assert state.current_spec.wing.sweep is not None
    assert state.current_spec.wing.sweep.value == 5.0


@pytest.mark.anyio
async def test_handle_modify_selected_part_set_tail_type(tmp_path):
    svc = _service_with_spec(tmp_path)
    state = svc.get_or_create_state("test-mod")
    events = [
        e async for e in svc._handle_modify_selected_part(
            state,
            {"part_ref": "part:tail", "operation": "set_tail_type", "value": "t-tail"},
            "tc-5",
        )
    ]
    assert any("generation_complete" in e for e in events)
    assert state.current_spec is not None
    assert state.current_spec.tail.type.value == "t-tail"


@pytest.mark.anyio
async def test_handle_modify_selected_part_invalid_combination(tmp_path):
    svc = _service_with_spec(tmp_path)
    state = svc.get_or_create_state("test-mod")
    events = [
        e async for e in svc._handle_modify_selected_part(
            state,
            {"part_ref": "part:fuselage", "operation": "set_span", "value": 14.0},
            "tc-6",
        )
    ]
    assert any("error" in e for e in events)
    assert state.current_spec is not None
    # Spec should not have changed
    assert state.current_spec.fuselage.length.value != 14.0


@pytest.mark.anyio
async def test_handle_modify_selected_part_engine_move_still_works(tmp_path):
    svc = _service_with_spec(tmp_path)
    state = svc.get_or_create_state("test-mod")
    events = [
        e async for e in svc._handle_modify_selected_part(
            state,
            {"part_ref": "part:right_engine", "operation": "move_outboard", "value": 0.5},
            "tc-7",
        )
    ]
    assert any("generation_complete" in e for e in events)
    assert state.current_spec is not None
    assert state.current_spec.engine.y_offset is not None
    assert state.current_spec.engine.y_offset.value == 0.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/z/codebase/aero-spec-agent && CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_chat_service.py -k "set_fuselage_length or set_wing_span or set_sweep or set_tail_type or invalid_combination or engine_move_still" -v`

Expected: FAIL — `_handle_modify_selected_part` still rejects non-engine parts and still reads `delta_m`.

- [ ] **Step 3: Rewrite `_handle_modify_selected_part`**

In `services/api/app/services/chat_service.py`, replace the entire `_handle_modify_selected_part` method (lines 695-793) with:

```python
    async def _handle_modify_selected_part(
        self, state: ConversationState, args: dict[str, Any], tool_call_id: str,
    ) -> AsyncIterator[str]:
        if state.current_spec is None:
            error_msg = "没有当前设计，请先使用 generate_design 创建设计"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({
                "role": "tool", "tool_call_id": tool_call_id,
                "content": json.dumps({"error": error_msg}, ensure_ascii=False),
            })
            return

        part_ref = args.get("part_ref", "")
        operation = args.get("operation", "")
        value = args.get("value")

        if not part_ref or not operation or value is None:
            error_msg = "缺少必要参数: part_ref, operation, value"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({
                "role": "tool", "tool_call_id": tool_call_id,
                "content": json.dumps({"error": error_msg}, ensure_ascii=False),
            })
            return

        data = state.current_spec.model_dump(mode="json")

        # --- engine move operations (incremental) ---
        if operation in self._ENGINE_MOVE_MAP:
            if part_ref not in ("part:left_engine", "part:right_engine"):
                error_msg = f"操作 {operation} 仅适用于发动机部件"
                yield _sse_event("error", {"content": error_msg})
                state.messages.append({
                    "role": "tool", "tool_call_id": tool_call_id,
                    "content": json.dumps({"error": error_msg}, ensure_ascii=False),
                })
                return

            offset_field, sign = self._ENGINE_MOVE_MAP[operation]
            new_delta = sign * float(value)
            offset_path = f"engine.{offset_field}"
            _pre_fill_none_scalars(data, [f"{offset_path}.value"])

            current_val = 0.0
            offset_scalar = data.get("engine", {}).get(offset_field)
            if isinstance(offset_scalar, dict) and "value" in offset_scalar:
                current_val = float(offset_scalar["value"])

            new_val = current_val + new_delta
            _set_nested(data, f"{offset_path}.value", new_val)
            _set_nested(data, f"{offset_path}.source", "user")
            _set_nested(data, f"{offset_path}.confidence", 1.0)
            _set_nested(data, f"{offset_path}.unit", "m")

        # --- set operations (absolute value) ---
        elif part_ref in self._PART_SET_OPERATIONS:
            ops = self._PART_SET_OPERATIONS[part_ref]
            if operation not in ops:
                error_msg = f"部件 {part_ref} 不支持操作 {operation}，可用: {', '.join(ops.keys())}"
                yield _sse_event("error", {"content": error_msg})
                state.messages.append({
                    "role": "tool", "tool_call_id": tool_call_id,
                    "content": json.dumps({"error": error_msg}, ensure_ascii=False),
                })
                return

            section, field_name, default_unit = ops[operation]
            field_path = f"{section}.{field_name}"
            _pre_fill_none_scalars(data, [f"{field_path}.value"])

            # tail.type is a TextScalar — value is a string
            if field_name == "type" and section == "tail":
                _set_nested(data, f"{field_path}.value", str(value))
            else:
                _set_nested(data, f"{field_path}.value", float(value))
            _set_nested(data, f"{field_path}.source", "user")
            _set_nested(data, f"{field_path}.confidence", 1.0)
            if default_unit:
                _set_nested(data, f"{field_path}.unit", default_unit)

        else:
            error_msg = f"不支持操作的部件: {part_ref}，或未知操作: {operation}"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({
                "role": "tool", "tool_call_id": tool_call_id,
                "content": json.dumps({"error": error_msg}, ensure_ascii=False),
            })
            return

        try:
            patched = AircraftSpec.model_validate(data)
        except Exception as exc:
            error_msg = f"spec patch 失败: {exc}"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({
                "role": "tool", "tool_call_id": tool_call_id,
                "content": json.dumps({"error": error_msg}, ensure_ascii=False),
            })
            return

        if self._job_runner is None:
            error_msg = "job runner not configured"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({
                "role": "tool", "tool_call_id": tool_call_id,
                "content": json.dumps({"error": error_msg}, ensure_ascii=False),
            })
            return

        yield _sse_event("generation_started", {"design_id": state.design_id})
        job = self._job_runner.generate(design_id=state.design_id, spec=patched)
        state.current_spec = patched

        result = {
            "status": job.status,
            "version_no": job.version_no,
            "design_id": job.design_id,
            "files": list(job.files.keys()),
            "error_message": job.error_message,
        }
        yield _sse_event("generation_complete", result)

        state.messages.append({
            "role": "tool", "tool_call_id": tool_call_id,
            "content": json.dumps(result, ensure_ascii=False),
        })
```

- [ ] **Step 4: Run all tests to verify**

Run: `cd /home/z/codebase/aero-spec-agent && CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_chat_service.py -v`

Expected: All tests PASS, including the new ones.

- [ ] **Step 5: Commit**

```bash
git add services/api/app/services/chat_service.py tests/api/test_chat_service.py
git commit -m "feat: rewrite _handle_modify_selected_part to support all aircraft parts"
```

---

### Task 3: Update existing schema test and system prompt

**Files:**
- Modify: `tests/api/test_chat_service.py:233-244`
- Modify: `services/api/app/services/chat_service.py:289-306`

- [ ] **Step 1: Update the existing schema test**

In `tests/api/test_chat_service.py`, replace `test_modify_selected_part_tool_schema` and `test_engine_move_map_covers_all_operations` (lines 233-244) with:

```python
def test_modify_selected_part_tool_schema():
    params = MODIFY_SELECTED_PART_TOOL["function"]["parameters"]
    assert "part_ref" in params["properties"]
    assert "operation" in params["properties"]
    assert "value" in params["properties"]
    assert params["required"] == ["part_ref", "operation", "value"]
    ops = params["properties"]["operation"]["enum"]
    assert "set_length" in ops
    assert "set_span" in ops
    assert "set_tail_type" in ops
    assert "move_outboard" in ops


def test_engine_move_map_covers_all_operations():
    ops = {op for op, _ in ChatService._ENGINE_MOVE_MAP.values()}
    assert ops == {"y_offset", "x_offset", "z_offset"}
    assert len(ChatService._ENGINE_MOVE_MAP) == 6


def test_part_set_operations_covers_fuselage_wing_tail():
    fuselage_ops = ChatService._PART_SET_OPERATIONS["part:fuselage"]
    assert "set_length" in fuselage_ops
    assert "set_diameter" in fuselage_ops
    wing_ops = ChatService._PART_SET_OPERATIONS["part:main_wing"]
    assert len(wing_ops) == 5
    tail_ops = ChatService._PART_SET_OPERATIONS["part:tail"]
    assert "set_tail_type" in tail_ops
```

- [ ] **Step 2: Update system prompt**

In `services/api/app/services/chat_service.py`, replace the `SYSTEM_PROMPT_TEMPLATE` (lines 289-306) with:

```python
SYSTEM_PROMPT_TEMPLATE = """你是 AeroSpec Agent，一个飞机概念设计助手。

用户用自然语言描述飞机需求，你负责生成或修改参数化设计。

当前设计状态：
%s

当前选中对象：
{selected_refs}

规则：
- 只处理固定翼无人机（fixed_wing_uav），常规布局（conventional）
- 新建设计使用 generate_design，修改现有设计使用 modify_design
- 用户引用当前选中部件（如"这个发动机""选中的机翼""这个机身"）并要求修改参数时，使用 modify_selected_part
- modify_selected_part 支持所有部件：机身(长度/直径)、机翼(翼展/弦长/后掠角/上反角)、尾翼(类型)、发动机(位置移动)
- 用户明确给出的参数直接填入，其余参数根据航空工程经验推断合理默认值
- 如果某些参数是你根据经验补全的，请把字段名放入 inferred_fields
- 生成完成后简要解释设计参数和依据
"""
```

- [ ] **Step 3: Run tests**

Run: `cd /home/z/codebase/aero-spec-agent && CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/ -v`

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add services/api/app/services/chat_service.py tests/api/test_chat_service.py
git commit -m "feat: update schema test and system prompt for all-part modification"
```

---

### Task 4: Update frontend labels and SpecSummary

**Files:**
- Modify: `apps/web/src/components/chat/ChatPanel.tsx:531-631`

- [ ] **Step 1: Update `OPERATION_LABELS`**

In `apps/web/src/components/chat/ChatPanel.tsx`, replace the `OPERATION_LABELS` object (lines 531-538) with:

```typescript
const OPERATION_LABELS: Record<string, string> = {
  set_length: "设置长度",
  set_diameter: "设置直径",
  set_span: "设置翼展",
  set_root_chord: "设置翼根弦长",
  set_tip_chord: "设置翼尖弦长",
  set_sweep: "设置后掠角",
  set_dihedral: "设置上反角",
  set_tail_type: "设置尾翼类型",
  move_outboard: "向外移动",
  move_inboard: "向内移动",
  move_forward: "向前移动",
  move_backward: "向后移动",
  move_up: "向上移动",
  move_down: "向下移动",
};
```

- [ ] **Step 2: Update `SpecSummary` for `modify_selected_part`**

In the same file, replace the `modify_selected_part` branch of `SpecSummary` (lines 580-601) with:

```typescript
    if (toolName === "modify_selected_part") {
      const partRef = String(args.part_ref ?? "");
      const operation = String(args.operation ?? "");
      const val = args.value;
      const isMove = operation.startsWith("move_");
      return (
        <div className="spec-summary">
          <div className="spec-summary-row">
            <span className="spec-summary-key">部件</span>
            <span className="spec-summary-val">{PART_REF_LABELS[partRef] ?? partRef}</span>
          </div>
          <div className="spec-summary-row">
            <span className="spec-summary-key">操作</span>
            <span className="spec-summary-val">
              {OPERATION_LABELS[operation] ?? operation}{" "}
              {isMove ? `${val} m` : val != null ? String(val) : ""}
            </span>
          </div>
          {args.reason != null && (
            <div className="spec-summary-row">
              <span className="spec-summary-key">原因</span>
              <span className="spec-summary-val">{String(args.reason)}</span>
            </div>
          )}
        </div>
      );
    }
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd /home/z/codebase/aero-spec-agent/apps/web && npx tsc --noEmit`

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/chat/ChatPanel.tsx
git commit -m "feat: update frontend operation labels and SpecSummary for all-part modification"
```

---

### Task 5: Full test suite

**Files:** None (verification only)

- [ ] **Step 1: Run full backend test suite**

Run: `cd /home/z/codebase/aero-spec-agent && CAD_BACKEND=fake .venv/bin/python -m pytest -q`

Expected: All tests pass.

- [ ] **Step 2: Run frontend type check**

Run: `cd /home/z/codebase/aero-spec-agent/apps/web && npx tsc --noEmit`

Expected: No errors.
