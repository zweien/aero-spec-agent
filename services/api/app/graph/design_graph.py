"""Design graph helpers.

Historically this module built a separate LangGraph (``build_design_graph``)
for shadow-mode intent comparison against the legacy ChatService classifier.
Shadow mode has been retired (see architecture review #1): there is now a
single intent classifier in ``graph/nodes/classify_intent.py``.

What remains is :func:`classify_message_intent`, a thin string-returning
adapter over the unified classifier, kept for callers (ChatService debug
logging, router scope guards) that compare against a ``DesignIntent`` literal.
"""

from __future__ import annotations

from services.api.app.graph.nodes.classify_intent import _classify
from services.api.app.graph.state import DesignIntent


def classify_message_intent(
    message: str,
    selected_refs: list[str] | None = None,
    has_current_spec: bool = False,
) -> DesignIntent:
    """Classify a message and return the intent literal.

    Thin adapter over the unified classifier (:func:`_classify`). Returns the
    intent string (or ``"conversation"`` when no design intent is detected) so
    callers can compare against ``DesignIntent`` literals without handling the
    full :class:`IntentResult`.
    """
    result = _classify(message, selected_refs, has_current_spec)
    return result.intent if result is not None else "conversation"
