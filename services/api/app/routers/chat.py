from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.api.app.graph.design_graph import run_shadow_classification
from services.api.app.graph.design_graph import classify_message_intent
from services.api.app.graph.mode import get_graph_mode
from services.api.app.graph.sse_adapter import convert_sse_events, sse_message_event
from services.api.app.graph.tracing import get_tracing_config
from services.api.app.services.chat_service import ChatService
from services.api.app.services.shadow_logger import ShadowLogger

router = APIRouter(prefix="/api", tags=["chat"])
chat_service = ChatService()
shadow_logger = ShadowLogger()


class ChatRequest(BaseModel):
    conversation_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    selected_refs: list[str] = Field(default_factory=list)


def set_job_runner(runner) -> None:
    chat_service.set_job_runner(runner)


@router.post("/chat")
async def chat(req: ChatRequest, background_tasks: BackgroundTasks):
    mode = get_graph_mode()

    if mode == "partial":
        return await _chat_partial(req, background_tasks)

    if mode == "shadow":
        return await _chat_shadow(req, background_tasks)

    # legacy (default)
    return StreamingResponse(
        chat_service.chat_stream(
            conversation_id=req.conversation_id,
            message=req.message,
            selected_refs=req.selected_refs,
            background_tasks=background_tasks,
        ),
        media_type="text/event-stream",
    )


async def _chat_shadow(req: ChatRequest, background_tasks: BackgroundTasks):
    """Shadow mode: legacy ChatService + LangGraph shadow logging."""
    state = chat_service.get_or_create_state(req.conversation_id)
    old_intent = classify_message_intent(
        req.message,
        selected_refs=req.selected_refs or None,
        has_current_spec=state.current_spec is not None,
    )

    new_result = run_shadow_classification(
        req.message,
        selected_refs=req.selected_refs or None,
        has_current_spec=state.current_spec is not None,
    )

    shadow_logger.log_divergence(
        conversation_id=req.conversation_id,
        user_message=req.message,
        old_result={"intent": old_intent},
        new_result={"intent": new_result["intent"], "tool_name": new_result.get("tool_name")},
    )

    return StreamingResponse(
        chat_service.chat_stream(
            conversation_id=req.conversation_id,
            message=req.message,
            selected_refs=req.selected_refs,
            background_tasks=background_tasks,
        ),
        media_type="text/event-stream",
    )


async def _chat_partial(req: ChatRequest, background_tasks: BackgroundTasks):
    """Partial mode: run LangGraph partial graph, fallback to legacy on error.

    Gray-release scope:
      - current_spec=None + generate_design → fallback legacy (no spec to enqueue)
      - selected_refs + current_spec → prefer partial
      - modify_design + current_spec → prefer partial
    """
    import logging
    logger = logging.getLogger(__name__)

    state = chat_service.get_or_create_state(req.conversation_id)
    has_spec = state.current_spec is not None if hasattr(state, "current_spec") else False

    # Pre-classify to decide if partial graph should handle this request
    intent = classify_message_intent(
        req.message,
        selected_refs=req.selected_refs or None,
        has_current_spec=has_spec,
    )

    # Scope guard: generate without spec must go through legacy (needs LLM)
    if intent == "generate_design" and not has_spec:
        return StreamingResponse(
            chat_service.chat_stream(
                conversation_id=req.conversation_id,
                message=req.message,
                selected_refs=req.selected_refs,
                background_tasks=background_tasks,
            ),
            media_type="text/event-stream",
        )

    try:
        from services.api.app.routers.designs import _get_job_runner

        job_runner = _get_job_runner()

        from services.api.app.graph.partial_graph import build_partial_design_graph
        graph = build_partial_design_graph(
            job_runner=job_runner,
            observe_until_terminal=False,
        )

        tracing_config = get_tracing_config(
            design_id=state.design_id if hasattr(state, "design_id") else "",
            conversation_id=req.conversation_id,
            graph_mode="partial",
        )

        input_state = {
            "conversation_id": req.conversation_id,
            "user_message": req.message,
            "selected_refs": req.selected_refs or [],
            "current_spec": state.current_spec.model_dump(mode="json") if has_spec else None,
        }
        if hasattr(state, "design_id") and state.design_id:
            input_state["design_id"] = state.design_id

        result = graph.invoke(input_state, config=tracing_config or None)

        # Check if the graph produced SSE events
        sse_events = result.get("sse_events", [])
        if sse_events:
            sse_lines = convert_sse_events(sse_events)
            # Add legacy chat response after SSE events
            import asyncio

            async def _partial_stream():
                for line in sse_lines:
                    yield line
                # Yield a final message event with content + metadata
                import json
                intent = result.get("intent", "unknown")
                job_id = result.get("job_id", "")
                status = result.get("status", "")
                content = _partial_message_content(intent, status)
                msg = json.dumps({
                    "content": content,
                    "intent": intent,
                    "job_id": job_id,
                    "status": status,
                })
                yield f"event: message\ndata: {msg}\n\n"

            return StreamingResponse(_partial_stream(), media_type="text/event-stream")

        # No SSE events (conversation intent) — fallback to legacy
        if result.get("intent") in ("conversation", "unknown"):
            return StreamingResponse(
                chat_service.chat_stream(
                    conversation_id=req.conversation_id,
                    message=req.message,
                    selected_refs=req.selected_refs,
                    background_tasks=background_tasks,
                ),
                media_type="text/event-stream",
            )

        # Graph ran but produced no events — fallback
        return StreamingResponse(
            chat_service.chat_stream(
                conversation_id=req.conversation_id,
                message=req.message,
                selected_refs=req.selected_refs,
                background_tasks=background_tasks,
            ),
            media_type="text/event-stream",
        )

    except Exception:
        logger.exception("partial graph failed, falling back to legacy")
        return StreamingResponse(
            chat_service.chat_stream(
                conversation_id=req.conversation_id,
                message=req.message,
                selected_refs=req.selected_refs,
                background_tasks=background_tasks,
            ),
            media_type="text/event-stream",
        )


@router.post("/chat/shadow")
async def chat_shadow(req: ChatRequest, background_tasks: BackgroundTasks):
    """Explicit shadow endpoint — always runs shadow regardless of CHAT_GRAPH_MODE."""
    return await _chat_shadow(req, background_tasks)


@router.post("/chat/stream")
async def chat_graph_stream(req: ChatRequest, background_tasks: BackgroundTasks):
    """Graph-native streaming: full lifecycle observation via JobEventBus.

    Uses observe_until_terminal=True with event_driven=True to stream
    generation_started → generation_progress → generation_complete/failed
    all from the graph, no frontend polling needed.
    """
    import asyncio
    import json
    import logging
    logger = logging.getLogger(__name__)

    state = chat_service.get_or_create_state(req.conversation_id)
    has_spec = state.current_spec is not None if hasattr(state, "current_spec") else False

    intent = classify_message_intent(
        req.message,
        selected_refs=req.selected_refs or None,
        has_current_spec=has_spec,
    )

    # Scope guard: generate without spec → legacy
    if intent == "generate_design" and not has_spec:
        return StreamingResponse(
            chat_service.chat_stream(
                conversation_id=req.conversation_id,
                message=req.message,
                selected_refs=req.selected_refs,
                background_tasks=background_tasks,
            ),
            media_type="text/event-stream",
        )

    # Conversation intent → legacy
    if intent in ("conversation", "unknown"):
        return StreamingResponse(
            chat_service.chat_stream(
                conversation_id=req.conversation_id,
                message=req.message,
                selected_refs=req.selected_refs,
                background_tasks=background_tasks,
            ),
            media_type="text/event-stream",
        )

    try:
        from services.api.app.routers.designs import _get_job_runner
        from services.api.app.graph.partial_graph import build_partial_design_graph
        from services.api.app.services.job_events import (
            JobEventType, get_job_event_bus,
        )

        job_runner = _get_job_runner()

        # Build graph with event-driven full lifecycle
        graph = build_partial_design_graph(
            job_runner=job_runner,
            observe_until_terminal=True,
            event_driven=True,
        )

        tracing_config = get_tracing_config(
            design_id=state.design_id if hasattr(state, "design_id") else "",
            conversation_id=req.conversation_id,
            graph_mode="partial",
        )

        input_state = {
            "conversation_id": req.conversation_id,
            "user_message": req.message,
            "selected_refs": req.selected_refs or [],
            "current_spec": state.current_spec.model_dump(mode="json") if has_spec else None,
        }
        if hasattr(state, "design_id") and state.design_id:
            input_state["design_id"] = state.design_id

        # Stream events from JobEventBus to SSE
        async def _graph_stream():
            bus = get_job_event_bus()
            event_queue: asyncio.Queue = asyncio.Queue()

            def _on_event(event):
                try:
                    event_queue.put_nowait(event)
                except Exception:
                    pass

            bus.subscribe(_on_event)

            # Run graph in thread pool to avoid blocking
            import concurrent.futures
            loop = asyncio.get_event_loop()

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = loop.run_in_executor(
                    pool,
                    lambda: graph.invoke(input_state, config=tracing_config or None),
                )

                # Stream events as they arrive
                terminal_event_received = False
                while not terminal_event_received:
                    try:
                        event = await asyncio.wait_for(event_queue.get(), timeout=0.5)
                    except asyncio.TimeoutError:
                        if future.done():
                            break
                        continue

                    if event.type in (
                        JobEventType.COMPLETED, JobEventType.FAILED,
                    ):
                        terminal_event_received = True

                    # Convert to SSE and yield
                    ev_dict = {
                        "event_type": event.type.value,
                        "job_id": event.job_id,
                        "design_id": event.design_id,
                        "version_no": event.version_no,
                        "status": "succeeded" if event.type == JobEventType.COMPLETED else "failed",
                        "progress": event.progress,
                        "current_step": event.current_step,
                        "duration_ms": event.duration_ms,
                        "error_message": event.error_message,
                        "created_at": event.timestamp,
                        "updated_at": event.timestamp,
                    }
                    from services.api.app.graph.sse_adapter import convert_sse_events
                    sse_lines = convert_sse_events([ev_dict])
                    for line in sse_lines:
                        yield line

                # Wait for graph to finish
                result = await future

                # Yield final message
                status = result.get("status", "")
                intent_val = result.get("intent", "")
                content = _partial_message_content(intent_val, status)
                yield sse_message_event(
                    content,
                    intent=intent_val,
                    job_id=result.get("job_id", ""),
                    status=status,
                )

            bus.unsubscribe(_on_event)

        return StreamingResponse(_graph_stream(), media_type="text/event-stream")

    except Exception:
        logger.exception("graph stream failed, falling back to legacy")
        return StreamingResponse(
            chat_service.chat_stream(
                conversation_id=req.conversation_id,
                message=req.message,
                selected_refs=req.selected_refs,
                background_tasks=background_tasks,
            ),
            media_type="text/event-stream",
        )


def _partial_message_content(intent: str, status: str) -> str:
    """Generate user-facing message content for partial mode response."""
    if status == "failed":
        return "生成任务提交失败，正在重试。"
    if intent in ("generate_design", "modify_design", "modify_selected_part"):
        return "已提交生成任务，正在后台生成 CAD 模型。"
    return "正在处理您的请求。"
