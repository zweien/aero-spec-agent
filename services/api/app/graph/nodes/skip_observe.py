"""skip_observe node — API-safe mode: skip polling, return immediately."""

from __future__ import annotations

from services.api.app.graph.state import DesignGraphState


def skip_observe(state: DesignGraphState) -> dict:
    """Skip job observation — used when observe_until_terminal=False.

    In API-safe mode, the graph enqueues the job and returns generation_started.
    Job completion is observed by the client via polling /api/jobs/{id}.
    Propagates failure from enqueue_job.
    """
    # If enqueue already failed, propagate the failure
    if state.get("status") == "failed":
        return {}
    return {"status": "queued"}
