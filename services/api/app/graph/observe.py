"""observe_node — decorator for logging LangGraph node execution metrics.

Wraps any graph node function to emit structured JSON logs with:
  - node name
  - execution latency (ms)
  - input state keys (not values, to avoid leaking large specs)
  - output state keys
  - success/failure status

Usage:
    from services.api.app.graph.observe import observe_node

    @observe_node("my_node")
    def my_node(state: MyState) -> dict:
        ...
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable

logger = logging.getLogger("aero.graph.observe")


def observe_node(name: str) -> Callable:
    """Decorator factory: wrap a graph node with observability logging."""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(state: dict[str, Any]) -> dict[str, Any]:
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
                raise

        return wrapper

    return decorator
