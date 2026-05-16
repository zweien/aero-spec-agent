from services.api.app.graph.design_graph import (
    DESIGN_GRAPH_NODES,
    DesignGraphState,
    classify_message_intent,
)


def test_design_graph_declares_required_nodes():
    assert DESIGN_GRAPH_NODES == (
        "load_context",
        "classify_intent",
        "generate_design",
        "modify_design",
        "submit_generation",
        "interpret_result",
    )


def test_design_graph_state_keeps_selected_refs():
    state = DesignGraphState(
        conversation_id="conv-1",
        design_id="design-1",
        user_message="change this",
        selected_refs=["part:right_engine"],
    )

    assert state["selected_refs"] == ["part:right_engine"]


# ---------------------------------------------------------------------------
# classify_message_intent
# ---------------------------------------------------------------------------

def test_classify_no_spec_as_generate_design():
    assert classify_message_intent(
        "设计一架双发无人机", has_current_spec=False,
    ) == "generate_design"


def test_classify_returns_generate_on_keyword():
    assert classify_message_intent(
        "生成一架长航时无人机", has_current_spec=True,
    ) == "generate_design"


def test_classify_existing_design_without_selected_ref_as_modify_design():
    assert classify_message_intent(
        "把翼展改成14米", has_current_spec=True,
    ) == "modify_design"


def test_classify_selected_ref_message_as_modify_selected_part():
    assert classify_message_intent(
        "把这个向外移动0.5米",
        selected_refs=["part:right_engine"],
        has_current_spec=True,
    ) == "modify_selected_part"
