"""LangSmith tracing configuration for LangGraph runs."""

from __future__ import annotations

import os


def is_tracing_enabled() -> bool:
    """Check if LangSmith tracing is enabled via environment variables."""
    return os.environ.get("LANGCHAIN_TRACING_V2", "").lower() in ("true", "1", "yes")


def get_tracing_project() -> str:
    """Get the LangSmith project name, defaulting to 'aero-spec-agent'."""
    return os.environ.get("LANGCHAIN_PROJECT", "aero-spec-agent")


def get_tracing_config() -> dict:
    """Return a LangSmith-compatible config for graph invocation.

    Only sets metadata when tracing is enabled; otherwise returns empty dict
    so that production runs are unaffected.
    """
    if not is_tracing_enabled():
        return {}

    return {
        "metadata": {
            "langchain_project": get_tracing_project(),
        },
        "tags": [f"project:{get_tracing_project()}"],
    }
