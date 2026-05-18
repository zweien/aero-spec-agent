"""prepare_tool_args node — validate and prepare AircraftSpec for job dispatch."""

from __future__ import annotations

from typing import TYPE_CHECKING

from services.api.app.graph.state import DesignGraphState

if TYPE_CHECKING:
    pass


def prepare_tool_args(state: DesignGraphState) -> dict:
    """Prepare tool arguments for the classified intent.

    Validates current_spec as AircraftSpec when available.
    For generate_design without a current_spec, sets a flag for enqueue_job.
    """
    intent = state.get("intent", "unknown")
    current_spec = state.get("current_spec")

    if intent in ("modify_design", "modify_selected_part") and current_spec:
        return {
            "aircraft_spec": current_spec,
            "tool_args": {
                "design_id": state.get("design_id", ""),
                "intent": intent,
            },
        }

    if intent == "generate_design" and current_spec:
        return {
            "aircraft_spec": current_spec,
            "tool_args": {
                "design_id": state.get("design_id", ""),
                "intent": intent,
            },
        }

    # No spec available — enqueue_job will handle the error
    return {
        "aircraft_spec": current_spec,
        "tool_args": {
            "design_id": state.get("design_id", ""),
            "intent": intent,
        },
        "error_message": "no spec available for job dispatch" if not current_spec else None,
    }
