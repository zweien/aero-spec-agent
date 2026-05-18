"""LangSmith tracing configuration for LangGraph runs."""

from __future__ import annotations

import os


def is_tracing_enabled() -> bool:
    """Check if LangSmith tracing is enabled via environment variables."""
    return os.environ.get("LANGCHAIN_TRACING_V2", "").lower() in ("true", "1", "yes")


def get_tracing_project() -> str:
    """Get the LangSmith project name, defaulting to 'aero-spec-agent'."""
    return os.environ.get("LANGCHAIN_PROJECT", "aero-spec-agent")


def get_tracing_config(
    design_id: str = "",
    conversation_id: str = "",
    graph_mode: str = "",
) -> dict:
    """Return a LangSmith-compatible config for graph invocation.

    Only sets metadata when tracing is enabled; otherwise returns empty dict
    so that production runs are unaffected.

    Args:
        design_id: Current design ID for trace metadata.
        conversation_id: Current conversation ID for trace metadata.
        graph_mode: Current graph mode (legacy/shadow/partial).
    """
    if not is_tracing_enabled():
        return {}

    metadata: dict[str, str] = {
        "langchain_project": get_tracing_project(),
    }
    if design_id:
        metadata["design_id"] = design_id
    if conversation_id:
        metadata["conversation_id"] = conversation_id
    if graph_mode:
        metadata["graph_mode"] = graph_mode

    return {
        "metadata": metadata,
        "tags": [f"project:{get_tracing_project()}"],
    }
