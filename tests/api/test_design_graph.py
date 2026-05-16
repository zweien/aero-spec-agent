from services.api.app.graph.design_graph import DESIGN_GRAPH_NODES, DesignGraphState


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
