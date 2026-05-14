import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.chat_service import (
    ChatService,
    ConversationState,
    SYSTEM_PROMPT_TEMPLATE,
)
from services.api.app.services.spec_io import load_aircraft_spec
from services.api.app.services.spec_patch import apply_patch


EXAMPLE = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


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
    spec = load_aircraft_spec(EXAMPLE)
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
    )
    data = state.to_dict()
    restored = ConversationState.from_dict(data)
    assert restored.conversation_id == "test-rt"
    assert len(restored.messages) == 1
    assert restored.current_spec is not None
    assert restored.current_spec.wing.span.value == spec.wing.span.value


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
