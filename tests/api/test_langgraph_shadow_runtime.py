"""Tests for LangGraph shadow-mode runtime — graph compilation, checkpointer,
would_call metadata, message accumulation, thread isolation, and streaming."""

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from services.api.app.graph.design_graph import build_design_graph, run_shadow_classification
from services.api.app.graph.state import DesignGraphState


# ---------------------------------------------------------------------------
# 1. Graph compilation (no checkpointer)
# ---------------------------------------------------------------------------


def test_graph_compiles_without_checkpointer():
    graph = build_design_graph()
    assert graph is not None
    result = graph.invoke({
        "conversation_id": "c1",
        "user_message": "设计一架无人机",
        "selected_refs": [],
        "current_spec": None,
    })
    assert result["intent"] == "generate_design"
    assert result["would_call_tool"] == "generate_design"


# ---------------------------------------------------------------------------
# 2. Graph compilation with InMemorySaver
# ---------------------------------------------------------------------------


def test_graph_compiles_with_checkpointer():
    checkpointer = InMemorySaver()
    graph = build_design_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "t1"}}
    result = graph.invoke(
        {
            "conversation_id": "c2",
            "user_message": "把翼展改成12米",
            "selected_refs": [],
            "current_spec": {},
        },
        config=config,
    )
    assert result["intent"] == "modify_design"
    assert result["would_call_tool"] == "modify_design"
    # State persisted — can retrieve via get_state
    snapshot = graph.get_state(config)
    assert snapshot.values["intent"] == "modify_design"


# ---------------------------------------------------------------------------
# 3. Message accumulation with add_messages reducer
# ---------------------------------------------------------------------------


def test_messages_accumulate_via_reducer():
    graph = build_design_graph()
    initial_messages = [HumanMessage(content="设计一架无人机")]
    result = graph.invoke({
        "conversation_id": "c3",
        "user_message": "设计一架无人机",
        "selected_refs": [],
        "current_spec": None,
        "messages": initial_messages,
    })
    # messages should contain the original HumanMessage (not overwritten)
    assert len(result["messages"]) >= 1
    assert isinstance(result["messages"][0], HumanMessage)


# ---------------------------------------------------------------------------
# 4. Thread isolation with checkpointer
# ---------------------------------------------------------------------------


def test_thread_isolation():
    checkpointer = InMemorySaver()
    graph = build_design_graph(checkpointer=checkpointer)

    config_a = {"configurable": {"thread_id": "thread-a"}}
    config_b = {"configurable": {"thread_id": "thread-b"}}

    graph.invoke({
        "conversation_id": "c4a",
        "user_message": "设计一架无人机",
        "selected_refs": [],
        "current_spec": None,
    }, config=config_a)

    graph.invoke({
        "conversation_id": "c4b",
        "user_message": "把翼展改成15米",
        "selected_refs": [],
        "current_spec": {},
    }, config=config_b)

    state_a = graph.get_state(config_a)
    state_b = graph.get_state(config_b)

    assert state_a.values["intent"] == "generate_design"
    assert state_b.values["intent"] == "modify_design"
    assert state_a.values["conversation_id"] == "c4a"
    assert state_b.values["conversation_id"] == "c4b"


# ---------------------------------------------------------------------------
# 5. Shadow classification returns would_call metadata
# ---------------------------------------------------------------------------


def test_shadow_classification_returns_would_call():
    result = run_shadow_classification("设计一架双发无人机", has_current_spec=False)
    assert result["intent"] == "generate_design"
    assert result["would_call_tool"] == "generate_design"
    assert isinstance(result["would_call_args"], dict)
    assert "message" in result["would_call_args"]


def test_shadow_classification_modify_selected_part():
    result = run_shadow_classification(
        "加长2米",
        selected_refs=["part:wing"],
        has_current_spec=True,
    )
    assert result["intent"] == "modify_selected_part"
    assert result["would_call_tool"] == "modify_selected_part"
    assert result["would_call_args"]["selected_refs"] == ["part:wing"]


# ---------------------------------------------------------------------------
# 6. astream_events v2 streaming
# ---------------------------------------------------------------------------


def test_astream_events_v2():
    """Test astream_events v2 via asyncio.run (sync pytest, async graph call)."""

    async def _run():
        checkpointer = InMemorySaver()
        graph = build_design_graph(checkpointer=checkpointer)
        input_state: DesignGraphState = {
            "conversation_id": "c6",
            "user_message": "设计一架无人机",
            "selected_refs": [],
            "current_spec": None,
        }
        config = {"configurable": {"thread_id": "stream-thread"}}

        events = []
        async for event in graph.astream_events(input_state, config=config, version="v2"):
            events.append(event)

        assert len(events) > 0
        event_names = [e["event"] for e in events]
        assert "on_chain_start" in event_names
        assert "on_chain_end" in event_names
        node_names = {e.get("name") for e in events}
        assert "load_context" in node_names
        assert "classify_intent" in node_names
        assert "generate_design" in node_names

    import asyncio
    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 7. graph_errors accumulation
# ---------------------------------------------------------------------------


def test_graph_errors_accumulate():
    graph = build_design_graph()
    result = graph.invoke({
        "conversation_id": "",  # triggers error in load_context
        "user_message": "设计一架无人机",
        "selected_refs": [],
        "current_spec": None,
    })
    # load_context writes error_message when conversation_id is empty
    assert result.get("error_message") == "missing conversation_id"
