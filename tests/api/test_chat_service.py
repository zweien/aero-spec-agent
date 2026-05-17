import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.api.app.services.chat_service import (
    ChatService,
    ConversationState,
    GENERATE_DESIGN_TOOL,
    MODIFY_DESIGN_TOOL,
    MODIFY_SELECTED_PART_TOOL,
    SYSTEM_PROMPT_TEMPLATE,
    _flat_args_to_spec,
    _pre_fill_none_scalars,
)
from services.api.app.services.job_runner import JobRecord, JobRunner
from services.api.app.services.selected_part_modifier import (
    ENGINE_MOVE_MAP,
    PART_SET_OPERATIONS,
)
from services.api.app.services.spec_io import load_aircraft_spec
from services.api.app.services.version_store import VersionStore
from services.workers.cad_worker.openvsp_generator.backend import FakeCadBackend


EXAMPLE = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")

MINIMAL_FLAT_ARGS = {
    "name": "test_uav",
    "fuselage_length": 5.0,
    "wing_position": "high",
    "wing_span": 10.0,
    "wing_root_chord": 1.0,
    "wing_tip_chord": 0.5,
    "tail_type": "conventional",
    "engine_count": 2,
}


def test_conversation_state_is_created():
    svc = ChatService()
    state = svc.get_or_create_state("conv-1")
    assert state.conversation_id == "conv-1"
    assert state.current_spec is None
    assert state.messages == []


def test_conversation_state_reuses_existing():
    svc = ChatService()
    state1 = svc.get_or_create_state("conv-1")
    state1.messages.append({"role": "user", "content": "hello"})
    state2 = svc.get_or_create_state("conv-1")
    assert len(state2.messages) == 1


def test_system_prompt_includes_current_spec():
    prompt = SYSTEM_PROMPT_TEMPLATE % "wing.span: 12.0"
    assert "wing.span: 12.0" in prompt
    assert "AeroSpec Agent" in prompt


def test_system_prompt_shows_no_design_when_empty():
    prompt = SYSTEM_PROMPT_TEMPLATE % "尚无设计"
    assert "尚无设计" in prompt


def test_build_tools_definitions():
    svc = ChatService()
    tools = svc.build_tools()
    names = [t["function"]["name"] for t in tools]
    assert "generate_design" in names
    assert "modify_design" in names
    assert "modify_selected_part" in names


def test_conversation_state_round_trip():
    spec = load_aircraft_spec(EXAMPLE)
    state = ConversationState(
        conversation_id="test-rt",
        design_id="test-rt",
        messages=[{"role": "user", "content": "hello"}],
        current_spec=spec,
        selected_refs=["part:right_engine"],
    )
    data = state.to_dict()
    restored = ConversationState.from_dict(data)
    assert restored.conversation_id == "test-rt"
    assert len(restored.messages) == 1
    assert restored.current_spec is not None
    assert restored.current_spec.wing.span.value == spec.wing.span.value
    assert restored.selected_refs == ["part:right_engine"]


def test_system_prompt_includes_selected_refs_context():
    svc = ChatService()
    state = ConversationState(
        conversation_id="selected-ctx",
        design_id="selected-ctx",
        selected_refs=["part:right_engine", "part:main_wing"],
    )

    prompt = svc._build_system_prompt(state)

    assert "当前选中对象" in prompt
    assert "part:right_engine" in prompt
    assert "part:main_wing" in prompt


def test_persistence_saves_and_loads(tmp_path):
    svc = ChatService(storage_root=tmp_path)
    state = svc.get_or_create_state("persist-1")
    state.messages.append({"role": "user", "content": "test msg"})
    state.current_spec = load_aircraft_spec(EXAMPLE)
    svc._save_state(state)

    svc2 = ChatService(storage_root=tmp_path)
    loaded = svc2.get_or_create_state("persist-1")
    assert len(loaded.messages) == 1
    assert loaded.messages[0]["content"] == "test msg"
    assert loaded.current_spec is not None


@pytest.mark.anyio
async def test_chat_stream_emits_error_event_when_llm_client_fails(monkeypatch):
    svc = ChatService()

    def fail_client():
        raise RuntimeError("missing llm credentials")

    monkeypatch.setattr(svc, "_get_client", fail_client)
    events = [
        event
        async for event in svc.chat_stream(
            conversation_id="llm-fail",
            message="hello",
            selected_refs=[],
        )
    ]

    assert len(events) == 1
    assert events[0].startswith("event: error")
    assert "missing llm credentials" in events[0]


@pytest.mark.anyio
async def test_chat_stream_logs_shadow_intent_for_selected_part_message(
    tmp_path,
    monkeypatch,
    caplog,
):
    svc = _service_with_spec(tmp_path)

    def fail_client():
        raise RuntimeError("stop before llm")

    monkeypatch.setattr(svc, "_get_client", fail_client)
    with caplog.at_level(logging.DEBUG, logger="services.api.app.services.chat_service"):
        events = [
            event
            async for event in svc.chat_stream(
                conversation_id="test-mod",
                message="把这个向外移动0.5米",
                selected_refs=["part:right_engine"],
            )
        ]

    assert events[0].startswith("event: error")
    assert "shadow_intent=modify_selected_part" in caplog.text


@pytest.mark.anyio
async def test_chat_stream_logs_shadow_intent_with_actual_tool(
    tmp_path,
    monkeypatch,
    caplog,
):
    svc = _service_with_spec(tmp_path)
    state = svc.get_or_create_state("test-mod")
    state.selected_refs = ["part:right_engine"]

    class AsyncChunks:
        def __init__(self, chunks):
            self._chunks = chunks

        def __aiter__(self):
            return self._iter()

        async def _iter(self):
            for chunk in self._chunks:
                yield chunk

    class FakeCompletions:
        async def create(self, *, tools=None, **kwargs):
            if tools:
                return AsyncChunks([
                    SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(
                                    content=None,
                                    tool_calls=[
                                        SimpleNamespace(
                                            index=0,
                                            id="tc-log",
                                            function=SimpleNamespace(
                                                name="modify_selected_part",
                                                arguments=json.dumps({
                                                    "part_ref": "part:right_engine",
                                                    "operation": "move_outboard",
                                                    "value": 0.5,
                                                }),
                                            ),
                                        )
                                    ],
                                ),
                                finish_reason="tool_calls",
                            )
                        ]
                    )
                ])
            return AsyncChunks([
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(content="完成"),
                            finish_reason="stop",
                        )
                    ]
                )
            ])

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    monkeypatch.setattr(svc, "_get_client", lambda: fake_client)

    with caplog.at_level(logging.DEBUG, logger="services.api.app.services.chat_service"):
        events = [
            event
            async for event in svc.chat_stream(
                conversation_id="test-mod",
                message="把这个向外移动0.5米",
                selected_refs=["part:right_engine"],
            )
        ]

    assert any(event.startswith("event: generation_complete") for event in events)
    assert '"shadow_intent": "modify_selected_part"' in caplog.text
    assert '"actual_tool": "modify_selected_part"' in caplog.text


# ---------------------------------------------------------------------------
# Flat args to spec conversion
# ---------------------------------------------------------------------------

def test_flat_args_to_spec_minimal():
    spec = _flat_args_to_spec(MINIMAL_FLAT_ARGS)
    assert spec.aircraft.name == "test_uav"
    assert spec.wing.span.value == 10.0
    assert spec.wing.span.unit == "m"
    assert spec.wing.span.source == "user"
    assert spec.engine.count.value == 2
    assert spec.fuselage.length.value == 5.0
    assert spec.fuselage.max_diameter is None
    assert spec.wing.sweep is None
    assert spec.mission.cruise_speed is None


def test_flat_args_to_spec_with_optional_fields():
    args = {
        **MINIMAL_FLAT_ARGS,
        "cruise_speed": 150,
        "wing_sweep": 5,
        "wing_airfoil": "NACA4412",
        "fuselage_diameter": 0.6,
        "payload": 30,
        "priority": "endurance",
    }
    spec = _flat_args_to_spec(args)
    assert spec.mission.cruise_speed is not None
    assert spec.mission.cruise_speed.value == 150
    assert spec.mission.cruise_speed.unit == "km/h"
    assert spec.wing.sweep is not None
    assert spec.wing.sweep.value == 5
    assert spec.wing.airfoil is not None
    assert spec.wing.airfoil.value == "NACA4412"
    assert spec.fuselage.max_diameter is not None
    assert spec.fuselage.max_diameter.value == 0.6


def test_flat_args_to_spec_rejects_missing_required():
    with pytest.raises(Exception):
        _flat_args_to_spec({"name": "bad"})


def test_flat_args_to_spec_inferred_fields():
    args = {
        **MINIMAL_FLAT_ARGS,
        "wing_sweep": 5,
        "fuselage_diameter": 0.6,
        "inferred_fields": ["wing_sweep", "fuselage_diameter"],
    }
    spec = _flat_args_to_spec(args)
    assert spec.wing.span.source == "user"
    assert spec.wing.span.confidence == 1.0
    assert spec.wing.sweep is not None
    assert spec.wing.sweep.source == "inferred"
    assert spec.wing.sweep.confidence == 0.75
    assert spec.fuselage.max_diameter is not None
    assert spec.fuselage.max_diameter.source == "inferred"


# ---------------------------------------------------------------------------
# Tool schema structure
# ---------------------------------------------------------------------------

def test_generate_design_tool_has_no_defs():
    assert "$defs" not in GENERATE_DESIGN_TOOL["function"]["parameters"]
    props = GENERATE_DESIGN_TOOL["function"]["parameters"]["properties"]
    assert "wing_span" in props
    assert "wing.position" not in props
    assert props["tail_type"]["enum"] == ["conventional"]
    assert props["engine_position"]["enum"] == ["under_wing"]


def test_modify_design_tool_has_field_enum():
    items = MODIFY_DESIGN_TOOL["function"]["parameters"]["properties"]["changes"]["items"]
    field_prop = items["properties"]["field"]
    assert "enum" in field_prop
    assert "wing_span" in field_prop["enum"]
    assert "fuselage_length" in field_prop["enum"]


# ---------------------------------------------------------------------------
# Pre-fill None scalars
# ---------------------------------------------------------------------------

def test_pre_fill_none_scalars():
    data = {"wing": {"sweep": None, "span": {"value": 10}}, "tail": {"type": None}}
    _pre_fill_none_scalars(data, ["wing.sweep.value"])
    assert data["wing"]["sweep"] == {}
    assert data["wing"]["span"] == {"value": 10}
    assert data["tail"]["type"] is None  # not affected


# ---------------------------------------------------------------------------
# modify_selected_part tool
# ---------------------------------------------------------------------------

def test_modify_selected_part_tool_schema():
    params = MODIFY_SELECTED_PART_TOOL["function"]["parameters"]
    assert "part_ref" in params["properties"]
    assert "operation" in params["properties"]
    assert "value" in params["properties"]
    assert params["required"] == ["part_ref", "operation", "value"]
    ops = params["properties"]["operation"]["enum"]
    assert "set_length" in ops
    assert "increase_length" in ops
    assert "decrease_span" in ops
    assert "set_span" in ops
    assert "set_tail_type" in ops
    assert "move_outboard" in ops


def test_engine_move_map_covers_all_operations():
    ops = {op for op, _ in ENGINE_MOVE_MAP.values()}
    assert ops == {"y_offset", "x_offset", "z_offset"}
    assert len(ENGINE_MOVE_MAP) == 6


def test_part_set_operations_covers_fuselage_wing_tail():
    fuselage_ops = PART_SET_OPERATIONS["part:fuselage"]
    assert "set_length" in fuselage_ops
    assert "set_diameter" in fuselage_ops
    wing_ops = PART_SET_OPERATIONS["part:main_wing"]
    assert len(wing_ops) == 5
    tail_ops = PART_SET_OPERATIONS["part:tail"]
    assert "set_tail_type" in tail_ops


# ---------------------------------------------------------------------------
# FakeJobRunner for handler tests
# ---------------------------------------------------------------------------


class FakeJobRunner:
    """Minimal job runner that returns a fake successful job."""

    def __init__(self, tmp_path: Path) -> None:
        self._store = VersionStore(tmp_path)
        self.generated_specs = []

    def generate(self, design_id: str, spec):
        self.generated_specs.append(spec)
        version_no, _ = self._store.create_version_dir(design_id)
        self._store.write_spec(design_id, version_no, spec)
        return JobRecord(
            id="fake-id",
            design_id=design_id,
            version_no=version_no,
            status="ready",
            progress=100,
            current_step="ready",
            files={"aircraft.vsp3": "fake"},
        )


def _service_with_spec(tmp_path: Path) -> ChatService:
    svc = ChatService(storage_root=tmp_path)
    svc.set_job_runner(FakeJobRunner(tmp_path))
    state = svc.get_or_create_state("test-mod")
    state.current_spec = load_aircraft_spec(EXAMPLE)
    return svc


def _sse_payload(event: str) -> dict[str, object]:
    data_line = next(line for line in event.splitlines() if line.startswith("data: "))
    return json.loads(data_line.removeprefix("data: "))


@pytest.mark.anyio
async def test_modify_design_rejects_unsupported_tail_type(tmp_path):
    svc = _service_with_spec(tmp_path)
    state = svc.get_or_create_state("test-mod")
    runner = svc._job_runner

    events = [
        e async for e in svc._handle_modify_design(
            state,
            {"changes": [{"field": "tail_type", "value": "t-tail"}]},
            "tc-tail-modify",
        )
    ]

    assert any(e.startswith("event: error") for e in events)
    assert runner.generated_specs == []


@pytest.mark.anyio
async def test_modify_design_rejects_unsupported_engine_position(tmp_path):
    svc = _service_with_spec(tmp_path)
    state = svc.get_or_create_state("test-mod")
    runner = svc._job_runner

    events = [
        e async for e in svc._handle_modify_design(
            state,
            {"changes": [{"field": "engine_position", "value": "rear_fuselage"}]},
            "tc-engine-position-modify",
        )
    ]

    assert any(e.startswith("event: error") for e in events)
    assert runner.generated_specs == []


@pytest.mark.anyio
async def test_modify_selected_part_set_fuselage_length_absolute(tmp_path):
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
async def test_modify_selected_part_rejects_unselected_part(tmp_path):
    svc = _service_with_spec(tmp_path)
    state = svc.get_or_create_state("test-mod")
    state.selected_refs = ["part:right_engine"]
    original_spec = state.current_spec
    runner = svc._job_runner

    events = [
        e async for e in svc._handle_modify_selected_part(
            state,
            {"part_ref": "part:left_engine", "operation": "move_outboard", "value": 0.5},
            "tc-unselected",
        )
    ]

    assert any(e.startswith("event: error") for e in events)
    assert "当前选中对象" in "".join(events)
    assert state.current_spec is original_spec
    assert runner.generated_specs == []


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
async def test_handle_modify_selected_part_set_sweep_when_actually_none(tmp_path):
    svc = _service_with_spec(tmp_path)
    state = svc.get_or_create_state("test-mod")
    state.current_spec = _flat_args_to_spec(MINIMAL_FLAT_ARGS)
    assert state.current_spec.wing.sweep is None

    events = [
        e async for e in svc._handle_modify_selected_part(
            state,
            {"part_ref": "part:main_wing", "operation": "set_sweep", "value": 7.0},
            "tc-sweep-none",
        )
    ]
    assert any("generation_complete" in e for e in events)
    assert state.current_spec.wing.sweep is not None
    assert state.current_spec.wing.sweep.value == 7.0


@pytest.mark.anyio
async def test_handle_modify_selected_part_set_tail_type(tmp_path):
    svc = _service_with_spec(tmp_path)
    state = svc.get_or_create_state("test-mod")
    events = [
        e async for e in svc._handle_modify_selected_part(
            state,
            {"part_ref": "part:tail", "operation": "set_tail_type", "value": "conventional"},
            "tc-5",
        )
    ]
    assert any("generation_complete" in e for e in events)
    assert state.current_spec is not None
    assert state.current_spec.tail.type.value == "conventional"


@pytest.mark.anyio
async def test_handle_modify_selected_part_rejects_unsupported_tail_type(tmp_path):
    svc = _service_with_spec(tmp_path)
    state = svc.get_or_create_state("test-mod")
    runner = svc._job_runner

    events = [
        e async for e in svc._handle_modify_selected_part(
            state,
            {"part_ref": "part:tail", "operation": "set_tail_type", "value": "t-tail"},
            "tc-tail-unsupported",
        )
    ]

    assert any(e.startswith("event: error") for e in events)
    assert runner.generated_specs == []


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
    assert state.current_spec.fuselage.length.value != 14.0


@pytest.mark.anyio
async def test_modify_selected_part_rejects_invalid_operation_for_part(tmp_path):
    svc = _service_with_spec(tmp_path)
    state = svc.get_or_create_state("test-mod")
    runner = svc._job_runner

    events = [
        e async for e in svc._handle_modify_selected_part(
            state,
            {"part_ref": "part:fuselage", "operation": "set_span", "value": 14.0},
            "tc-invalid-op",
        )
    ]

    assert any(e.startswith("event: error") for e in events)
    assert runner.generated_specs == []


@pytest.mark.anyio
async def test_modify_selected_part_move_right_engine_outboard_updates_engine_y_offset(tmp_path):
    svc = _service_with_spec(tmp_path)
    state = svc.get_or_create_state("test-mod")
    state.selected_refs = ["part:right_engine"]
    events = [
        e async for e in svc._handle_modify_selected_part(
            state,
            {"part_ref": "part:right_engine", "operation": "move_outboard", "value": 0.5},
            "tc-7",
        )
    ]
    assert any("generation_complete" in e for e in events)
    assert "已基于选中对象 part:right_engine 完成修改。" in "".join(events)
    assert state.current_spec is not None
    assert state.current_spec.engine.y_offset is not None
    assert state.current_spec.engine.y_offset.value == 0.5


@pytest.mark.anyio
async def test_modify_selected_part_end_to_end_generates_version_and_validates_engine_offset(
    tmp_path,
):
    store = VersionStore(tmp_path)
    runner = JobRunner(store=store, backend=FakeCadBackend())
    svc = ChatService(storage_root=tmp_path)
    svc.set_job_runner(runner)
    state = svc.get_or_create_state("selected-e2e")
    state.current_spec = load_aircraft_spec(EXAMPLE)
    state.selected_refs = ["part:right_engine"]
    runner.generate(design_id=state.design_id, spec=state.current_spec)

    events = [
        e async for e in svc._handle_modify_selected_part(
            state,
            {"part_ref": "part:right_engine", "operation": "move_outboard", "value": 0.5},
            "tc-e2e",
        )
    ]

    complete_event = next(e for e in events if e.startswith("event: generation_complete"))
    complete_payload = _sse_payload(complete_event)
    assert complete_payload["version_no"] == 2
    assert state.current_spec is not None
    assert state.current_spec.engine.y_offset is not None
    assert state.current_spec.engine.y_offset.value == 0.5

    version = store.read_version(state.design_id, 2)
    validation_report = version["validation_report"]
    assert validation_report["engine.y_offset"] == {
        "expected": 0.5,
        "actual": 0.5,
        "status": "pass",
    }


@pytest.mark.anyio
async def test_modify_selected_part_increase_fuselage_length(tmp_path):
    svc = _service_with_spec(tmp_path)
    state = svc.get_or_create_state("test-mod")
    state.selected_refs = ["part:fuselage"]

    events = [
        e async for e in svc._handle_modify_selected_part(
            state,
            {"part_ref": "part:fuselage", "operation": "increase_length", "value": 2.0},
            "tc-increase-length",
        )
    ]

    assert any("generation_complete" in e for e in events)
    assert state.current_spec is not None
    assert state.current_spec.fuselage.length.value == 9.0
    assert state.current_spec.fuselage.length.unit == "m"
    assert state.current_spec.fuselage.length.source == "user"


@pytest.mark.anyio
async def test_modify_selected_part_decrease_wing_span(tmp_path):
    svc = _service_with_spec(tmp_path)
    state = svc.get_or_create_state("test-mod")
    state.selected_refs = ["part:main_wing"]

    events = [
        e async for e in svc._handle_modify_selected_part(
            state,
            {"part_ref": "part:main_wing", "operation": "decrease_span", "value": 2.0},
            "tc-decrease-span",
        )
    ]

    assert any("generation_complete" in e for e in events)
    assert state.current_spec is not None
    assert state.current_spec.wing.span.value == 10.0
    assert state.current_spec.wing.span.unit == "m"


@pytest.mark.anyio
async def test_modify_selected_part_rejects_non_positive_length(tmp_path):
    svc = _service_with_spec(tmp_path)
    state = svc.get_or_create_state("test-mod")
    state.selected_refs = ["part:fuselage"]
    original_length = state.current_spec.fuselage.length.value
    runner = svc._job_runner

    events = [
        e async for e in svc._handle_modify_selected_part(
            state,
            {"part_ref": "part:fuselage", "operation": "decrease_length", "value": original_length},
            "tc-non-positive",
        )
    ]

    assert any(e.startswith("event: error") for e in events)
    assert state.current_spec is not None
    assert state.current_spec.fuselage.length.value == original_length
    assert runner.generated_specs == []


def test_generate_design_marks_inferred_fields_as_inferred():
    args = {
        **MINIMAL_FLAT_ARGS,
        "wing_sweep": 5,
        "fuselage_diameter": 0.6,
        "inferred_fields": ["wing_sweep", "fuselage_diameter"],
    }

    spec = _flat_args_to_spec(args)

    assert spec.wing.sweep is not None
    assert spec.wing.sweep.source == "inferred"
    assert spec.fuselage.max_diameter is not None
    assert spec.fuselage.max_diameter.source == "inferred"
