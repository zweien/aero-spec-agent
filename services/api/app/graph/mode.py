"""Graph mode switch — CHAT_GRAPH_MODE=legacy|shadow|partial."""

from __future__ import annotations

import os
from typing import Literal

GraphMode = Literal["legacy", "shadow", "partial"]


def get_graph_mode() -> GraphMode:
    """Read CHAT_GRAPH_MODE from environment.

    - legacy: existing ChatService, no graph involvement.
    - shadow: legacy + LangGraph shadow classification + divergence logging.
    - partial: prefer LangGraph partial graph, fallback to legacy on error.
    """
    mode = os.environ.get("CHAT_GRAPH_MODE", "legacy").lower()
    if mode not in ("legacy", "shadow", "partial"):
        return "legacy"
    return mode
