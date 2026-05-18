"""observe_node_sse — like observe_node but also publishes graph_node events to JobEventBus.

Emits a custom SSE event type 'graph_node' with:
  - node: name
  - status: started / completed / failed
  - latency_ms: elapsed time (only on completed/failed)
  - output_keys: keys from the node output (only on completed)
"""

from __future__ import annotations

import functools
import json
import logging
import time
from typing import Any, Callable

logger = logging.getLogger("aero.graph.observe")


def _publish_graph_node(design_id: str, node: str, status: str, **extra: Any) -> None:
    """Publish a graph_node event to JobEventBus."""
    try:
        from services.api.app.services.job_events import get_job_event_bus

        bus = get_job_event_bus()
        event_data = {
            "event_type": "graph_node",
            "design_id": design_id,
            "node": node,
            "status": status,
            **extra,
        }
        # Use a synthetic JobEvent to carry custom data through the bus
        from services.api.app.services.job_events import JobEvent, JobEventType

        event = JobEvent(
            type=JobEventType.PROGRESS,
            job_id=f"graph:{design_id}",
            design_id=design_id,
            version_no=0,
            current_step=node,
            progress=0,
        )
        # Attach extra data as a side channel
        event._graph_node_data = event_data  # type: ignore[attr-defined]
        bus.publish(event)
    except Exception:
        logger.debug("Failed to publish graph_node event", exc_info=True)


def observe_node_sse(name: str) -> Callable:
    """Decorator: observe_node + publish graph_node SSE events."""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(state: dict[str, Any]) -> dict[str, Any]:
            design_id = state.get("design_id", "")
            _publish_graph_node(design_id, name, "started")

            t0 = time.monotonic()
            input_keys = sorted(state.keys())
            try:
                result = fn(state)
                elapsed_ms = (time.monotonic() - t0) * 1000
                output_keys = sorted(result.keys()) if isinstance(result, dict) else []
                logger.info(
                    "node_completed",
                    extra={
                        "node": name,
                        "latency_ms": round(elapsed_ms, 2),
                        "input_keys": input_keys,
                        "output_keys": output_keys,
                        "status": "ok",
                    },
                )
                _publish_graph_node(
                    design_id, name, "completed",
                    latency_ms=round(elapsed_ms, 2),
                    output_keys=output_keys,
                )
                return result
            except Exception:
                elapsed_ms = (time.monotonic() - t0) * 1000
                logger.exception(
                    "node_failed",
                    extra={
                        "node": name,
                        "latency_ms": round(elapsed_ms, 2),
                        "input_keys": input_keys,
                        "status": "error",
                    },
                )
                _publish_graph_node(
                    design_id, name, "failed",
                    latency_ms=round(elapsed_ms, 2),
                )
                raise

        return wrapper

    return decorator
