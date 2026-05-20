from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.api.app.graph.deep_design_graph import build_deep_design_graph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["deep-design"])


class DeepDesignRequest(BaseModel):
    design_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    base_spec: dict[str, Any]
    constraints: dict[str, Any] = Field(default_factory=dict)


class DeepDesignResponse(BaseModel):
    design_id: str
    status: str
    report: str = ""
    comparison: dict[str, Any] | None = None
    error_message: str | None = None


def _get_runner():
    try:
        from services.api.app.routers.designs import _get_job_runner
        return _get_job_runner()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="job runner not available") from exc


def _sse(event_type: str, data: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def _job_event_to_sse(event) -> str | None:
    """Convert a JobEvent to an SSE string."""
    # Check for graph_node custom data first
    graph_data = getattr(event, "_graph_node_data", None)
    if graph_data:
        return _sse("graph_node", graph_data)

    # Map standard job events
    from services.api.app.graph.sse_adapter import convert_job_event_to_sse
    evt_dict = {
        "type": event.type.value if hasattr(event.type, "value") else str(event.type),
        "job_id": event.job_id,
        "design_id": event.design_id,
        "version_no": event.version_no,
        "progress": event.progress,
        "current_step": event.current_step,
    }
    if event.error_message:
        evt_dict["error_message"] = event.error_message
    if event.duration_ms is not None:
        evt_dict["duration_ms"] = event.duration_ms
    if getattr(event, "stage", ""):
        evt_dict["stage"] = event.stage
    if getattr(event, "label", ""):
        evt_dict["label"] = event.label
    if getattr(event, "metadata", None):
        evt_dict["metadata"] = event.metadata
    return convert_job_event_to_sse(evt_dict)


@router.post("/deep-design", response_model=DeepDesignResponse)
async def deep_design(req: DeepDesignRequest, background_tasks: BackgroundTasks):
    """Run multi-variant design exploration.

    Phase 1: parse requirements, dispatch N variant jobs, wait, compare, report.
    """
    job_runner = _get_runner()
    graph = build_deep_design_graph(job_runner=job_runner, timeout_seconds=120)

    try:
        result = graph.invoke({
            "user_description": req.description,
            "design_id": req.design_id,
            "base_spec": req.base_spec,
            "constraints": req.constraints,
        })
    except Exception as exc:
        logger.exception("deep-design graph failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Record metrics
    try:
        from services.api.app.graph.metrics import get_metrics_collector
        import time as _time

        comparison = result.get("comparison")
        mc = get_metrics_collector()
        mc.record_deep_design(
            duration_ms=0,
            status=result.get("status", "unknown"),
            variants=comparison.get("total_variants", 0) if comparison else 0,
            succeeded=comparison.get("succeeded", 0) if comparison else 0,
        )
    except Exception:
        logger.debug("Failed to record deep_design metrics", exc_info=True)

    return DeepDesignResponse(
        design_id=req.design_id,
        status=result.get("status", "unknown"),
        report=result.get("report", ""),
        comparison=result.get("comparison"),
        error_message=result.get("error_message"),
    )


@router.post("/deep-design/stream")
async def deep_design_stream(req: DeepDesignRequest):
    """SSE streaming for deep-design graph execution.

    Events emitted:
      - graph_node: node started/completed/failed with latency
      - generation_started: variant job started
      - generation_progress: variant job progress
      - generation_complete: variant job succeeded
      - generation_failed: variant job failed
      - message: final result summary
    """
    job_runner = _get_runner()
    graph = build_deep_design_graph(
        job_runner=job_runner, timeout_seconds=120, streaming=True,
    )

    input_state = {
        "user_description": req.description,
        "design_id": req.design_id,
        "base_spec": req.base_spec,
        "constraints": req.constraints,
    }

    async def _stream():
        from services.api.app.services.job_events import get_job_event_bus

        bus = get_job_event_bus()
        event_queue = bus.async_queue()
        loop = asyncio.get_event_loop()

        yield _sse("message", {"content": "Deep design exploration started", "design_id": req.design_id})

        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = loop.run_in_executor(
                pool,
                lambda: graph.invoke(input_state),
            )

            while True:
                if future.done():
                    # Drain remaining events
                    while not event_queue.empty():
                        try:
                            event = event_queue.get_nowait()
                            sse_str = _job_event_to_sse(event)
                            if sse_str:
                                yield sse_str
                        except asyncio.QueueEmpty:
                            break
                    break

                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue

                sse_str = _job_event_to_sse(event)
                if sse_str:
                    yield sse_str

            # Wait for result and yield final message
            try:
                result = await future
                yield _sse("message", {
                    "content": result.get("report", "Design exploration completed"),
                    "design_id": req.design_id,
                    "status": result.get("status", "completed"),
                })
            except Exception as exc:
                yield _sse("message", {
                    "content": f"Design exploration failed: {exc}",
                    "design_id": req.design_id,
                    "status": "failed",
                })

        bus.release_async_queue(event_queue)

    return StreamingResponse(_stream(), media_type="text/event-stream")
