"""Graph mode switch — CHAT_GRAPH_MODE=legacy|partial.

Shadow mode has been retired (single intent classifier now — see architecture
review #1). Only legacy (ChatService) and partial (LangGraph partial graph)
remain.
"""

from __future__ import annotations

import os
from typing import Literal

GraphMode = Literal["legacy", "partial"]


def get_graph_mode() -> GraphMode:
    """Read CHAT_GRAPH_MODE from environment.

    - legacy: existing ChatService, no graph involvement.
    - partial: prefer LangGraph partial graph, fallback to legacy on error.
    """
    mode = os.environ.get("CHAT_GRAPH_MODE", "legacy").lower()
    if mode not in ("legacy", "partial"):
        return "legacy"
    return mode
