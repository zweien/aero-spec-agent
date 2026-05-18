"""Design graph — LangGraph StateGraph for design orchestration."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from services.api.app.graph.state import DesignGraphState
from services.api.app.graph.nodes.load_context import load_context
from services.api.app.graph.nodes.classify_intent import classify_intent
from services.api.app.graph.nodes.generate_design import generate_design
from services.api.app.graph.nodes.modify_design import modify_design
from services.api.app.graph.nodes.modify_selected_part import modify_selected_part
from services.api.app.graph.nodes.save_state import save_state

logger = logging.getLogger(__name__)


def _route_by_intent(state: DesignGraphState) -> str:
    """Conditional edge: route to the tool node matching classified intent."""
    intent = state.get("intent", "unknown")
    routing = {
        "generate_design": "generate_design",
        "modify_design": "modify_design",
        "modify_selected_part": "modify_selected_part",
        "conversation": "save_state",
        "unknown": "save_state",
    }
    target = routing.get(intent, "save_state")
    logger.debug("graph routing: intent=%s → node=%s", intent, target)
    return target


def build_design_graph() -> StateGraph:
    """Build the design orchestration graph.

    Flow:
        START → load_context → classify_intent
        → {generate|modify|modify_selected_part} → save_state → END

    In shadow mode, only load_context and classify_intent execute meaningfully.
    Tool nodes return metadata for divergence comparison.
    """
    graph = StateGraph(DesignGraphState)

    # Add nodes
    graph.add_node("load_context", load_context)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("generate_design", generate_design)
    graph.add_node("modify_design", modify_design)
    graph.add_node("modify_selected_part", modify_selected_part)
    graph.add_node("save_state", save_state)

    # Entry: START → load_context
    graph.add_edge(START, "load_context")

    # Linear: load_context → classify_intent
    graph.add_edge("load_context", "classify_intent")

    # Conditional: classify_intent → tool node or save_state
    graph.add_conditional_edges(
        "classify_intent",
        _route_by_intent,
        {
            "generate_design": "generate_design",
            "modify_design": "modify_design",
            "modify_selected_part": "modify_selected_part",
            "save_state": "save_state",
        },
    )

    # All tool nodes → save_state
    graph.add_edge("generate_design", "save_state")
    graph.add_edge("modify_design", "save_state")
    graph.add_edge("modify_selected_part", "save_state")

    # save_state → END
    graph.add_edge("save_state", END)

    return graph


def run_shadow_classification(
    message: str,
    selected_refs: list[str] | None = None,
    has_current_spec: bool = False,
) -> dict[str, Any]:
    """Run the LangGraph for shadow-mode intent classification.

    Returns the graph state after execution for divergence comparison.
    """
    g = build_design_graph().compile()
    initial_state: DesignGraphState = {
        "conversation_id": "shadow",
        "user_message": message,
        "selected_refs": selected_refs or [],
        "current_spec": {} if has_current_spec else None,
    }
    result = g.invoke(initial_state)
    return {
        "intent": result.get("intent", "unknown"),
        "tool_name": result.get("tool_name"),
    }


# Backward-compatible alias for ChatService
def classify_message_intent(
    message: str,
    selected_refs: list[str] | None = None,
    has_current_spec: bool = False,
) -> str:
    """Legacy intent classifier, delegates to the classify_intent node logic."""
    from services.api.app.graph.nodes.classify_intent import _classify
    return _classify(message, selected_refs, has_current_spec)
