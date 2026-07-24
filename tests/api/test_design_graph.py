"""Tests for design_graph.classify_message_intent (backward-compat adapter).

The shadow-mode graph (build_design_graph / run_shadow_classification) has
been retired. classify_message_intent remains as a thin adapter over the
unified classifier; intent classification itself is tested in
test_intent_classifier.py.
"""

from services.api.app.graph.design_graph import classify_message_intent
from services.api.app.graph.state import DesignGraphState


def test_design_graph_state_keeps_selected_refs():
    state = DesignGraphState(
        conversation_id="conv-1",
        design_id="design-1",
        user_message="change this",
        selected_refs=["part:right_engine"],
    )

    assert state["selected_refs"] == ["part:right_engine"]


# ---------------------------------------------------------------------------
# classify_message_intent (backward-compat adapter over the unified classifier)
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


def test_classify_informational_as_conversation():
    assert classify_message_intent("什么是升阻比") == "conversation"
