from pathlib import Path

import pytest

from services.api.app.services.chat_service import (
    ChatService,
    ConversationState,
    GENERATE_DESIGN_TOOL,
    MODIFY_DESIGN_TOOL,
    SYSTEM_PROMPT_TEMPLATE,
    _flat_args_to_spec,
    _pre_fill_none_scalars,
)
from services.api.app.services.spec_io import load_aircraft_spec


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


# ---------------------------------------------------------------------------
# Tool schema structure
# ---------------------------------------------------------------------------

def test_generate_design_tool_has_no_defs():
    assert "$defs" not in GENERATE_DESIGN_TOOL["function"]["parameters"]
    props = GENERATE_DESIGN_TOOL["function"]["parameters"]["properties"]
    assert "wing_span" in props
    assert "wing.position" not in props


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
