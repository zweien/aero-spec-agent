"""Partial mode graph — LangGraph orchestration with real job dispatch.

This graph replaces the ChatService tool dispatch chain while
preserving fallback to the old path on failure.

Flow:
    START → load_context → classify_intent → prepare_tool_args
    → enqueue_job → observe_job → emit_sse → save_state → END

Conversation/unknown intents short-circuit to save_state.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from services.api.app.graph.state import DesignGraphState
from services.api.app.graph.nodes.load_context import load_context
from services.api.app.graph.nodes.classify_intent import classify_intent
from services.api.app.graph.nodes.prepare_tool_args import prepare_tool_args
from services.api.app.graph.nodes.enqueue_job import make_enqueue_job_node
from services.api.app.graph.nodes.observe_job import make_observe_job_node
from services.api.app.graph.nodes.emit_sse import emit_sse
from services.api.app.graph.nodes.save_state import save_state

logger = logging.getLogger(__name__)


def _route_by_intent(state: DesignGraphState) -> str:
    """Route: tool intents → prepare_tool_args, others → save_state."""
    intent = state.get("intent", "unknown")
    if intent in ("generate_design", "modify_design", "modify_selected_part"):
        return "prepare_tool_args"
    return "save_state"


def build_partial_design_graph(
    job_runner: Any,
    checkpointer: InMemorySaver | None = None,
    poll_interval: float = 0.3,
    max_poll_seconds: float = 120,
) -> StateGraph:
    """Build the partial-mode design orchestration graph.

    Args:
        job_runner: JobRunner instance for enqueue/observe operations.
        checkpointer: Optional checkpointer for thread-based persistence.
        poll_interval: Seconds between job status polls.
        max_poll_seconds: Maximum time to wait for job completion.

    Returns:
        Compiled StateGraph ready for invoke/astream_events.
    """
    graph = StateGraph(DesignGraphState)

    # Add nodes — enqueue_job and observe_job use factory pattern for DI
    graph.add_node("load_context", load_context)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("prepare_tool_args", prepare_tool_args)
    graph.add_node("enqueue_job", make_enqueue_job_node(job_runner))
    graph.add_node("observe_job", make_observe_job_node(
        job_runner, poll_interval=poll_interval, max_poll_seconds=max_poll_seconds,
    ))
    graph.add_node("emit_sse", emit_sse)
    graph.add_node("save_state", save_state)

    # Edges
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "classify_intent")

    # Conditional: tool intents go to prepare_tool_args, others to save_state
    graph.add_conditional_edges(
        "classify_intent",
        _route_by_intent,
        {
            "prepare_tool_args": "prepare_tool_args",
            "save_state": "save_state",
        },
    )

    # Tool path: prepare → enqueue → observe → emit → save
    graph.add_edge("prepare_tool_args", "enqueue_job")
    graph.add_edge("enqueue_job", "observe_job")
    graph.add_edge("observe_job", "emit_sse")
    graph.add_edge("emit_sse", "save_state")

    # save_state → END
    graph.add_edge("save_state", END)

    return graph.compile(checkpointer=checkpointer)
