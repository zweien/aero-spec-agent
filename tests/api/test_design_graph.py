from services.api.app.graph.design_graph import (
    build_design_graph,
    classify_message_intent,
    run_shadow_classification,
)
from services.api.app.graph.state import DesignGraphState


def test_build_design_graph_compiles():
    graph = build_design_graph()
    compiled = graph.compile()
    assert compiled is not None


def test_design_graph_state_keeps_selected_refs():
    state = DesignGraphState(
        conversation_id="conv-1",
        design_id="design-1",
        user_message="change this",
        selected_refs=["part:right_engine"],
    )

    assert state["selected_refs"] == ["part:right_engine"]


# ---------------------------------------------------------------------------
# classify_message_intent (backward-compat)
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


# ---------------------------------------------------------------------------
# LangGraph shadow classification
# ---------------------------------------------------------------------------

def test_shadow_classification_generate():
    result = run_shadow_classification("设计一架无人机", has_current_spec=False)
    assert result["intent"] == "generate_design"
    assert result["tool_name"] == "generate_design"


def test_shadow_classification_modify():
    result = run_shadow_classification(
        "把翼展改成15米",
        selected_refs=[],
        has_current_spec=True,
    )
    assert result["intent"] == "modify_design"


def test_shadow_classification_selected_part():
    result = run_shadow_classification(
        "加长2米",
        selected_refs=["part:wing"],
        has_current_spec=True,
    )
    assert result["intent"] == "modify_selected_part"
