from fastapi import APIRouter, BackgroundTasks, HTTPException
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

        # Stream events from async JobEventBus to SSE
        async def _graph_stream():
            bus = get_job_event_bus()
            event_queue = bus.async_queue()

            # Run graph in thread pool to avoid blocking
            import concurrent.futures
            loop = asyncio.get_event_loop()

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = loop.run_in_executor(
                    pool,
                    lambda: graph.invoke(input_state, config=tracing_config or None),
                )

                # Stream events from async queue
                while True:
                    if future.done():
                        # Drain remaining events
                        while not event_queue.empty():
                            event = event_queue.get_nowait()
                            async for line in _event_to_sse(event):
                                yield line
                        break

                    try:
                        event = await asyncio.wait_for(event_queue.get(), timeout=0.5)
                    except asyncio.TimeoutError:
                        continue

                    async for line in _event_to_sse(event):
                        yield line

                # Wait for graph result
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

            bus.release_async_queue(event_queue)

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


async def _event_to_sse(event):
    """Convert a JobEvent to SSE lines."""
    from services.api.app.graph.sse_adapter import convert_sse_events
    from services.api.app.services.job_events import JobEventType
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
    sse_lines = convert_sse_events([ev_dict])
    for line in sse_lines:
        yield line


# --- Endpoints for AI SDK route handler ---


@router.get("/conversations/{conversation_id}/state")
async def get_conversation_state(conversation_id: str):
    """Return conversation state for the Next.js route handler to build the system prompt."""
    state = chat_service.get_or_create_state(conversation_id)

    spec_yaml = None
    if state.current_spec is not None:
        from services.api.app.services.spec_io import dump_aircraft_spec
        from pathlib import Path
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            dump_aircraft_spec(state.current_spec, Path(f.name))
            spec_yaml = Path(f.name).read_text(encoding="utf-8")
        Path(f.name).unlink(missing_ok=True)

    return {
        "design_id": getattr(state, "design_id", None),
        "current_spec_yaml": spec_yaml,
        "selected_refs": getattr(state, "selected_refs", []),
    }


class ToolExecuteRequest(BaseModel):
    conversation_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    args: dict = Field(default_factory=dict)


@router.post("/tools/execute")
async def tool_execute(req: ToolExecuteRequest, background_tasks: BackgroundTasks):
    """Execute a tool call on behalf of the AI SDK route handler.

    Reuses ChatService's tool execution logic (spec conversion, job enqueue).
    Returns immediately with job_id for async processing.
    """
    state = chat_service.get_or_create_state(req.conversation_id)

    if req.tool_name == "generate_design":
        return await _tool_generate(state, req.args, background_tasks)
    elif req.tool_name == "modify_design":
        return await _tool_modify(state, req.args, background_tasks)
    elif req.tool_name == "modify_selected_part":
        return await _tool_modify_selected(state, req.args, background_tasks)
    else:
        raise HTTPException(status_code=400, detail=f"unknown tool: {req.tool_name}")


async def _tool_generate(state, args: dict, background_tasks: BackgroundTasks):
    from services.api.app.routers.designs import _get_job_runner
    from services.api.app.services.chat_service import _flat_args_to_spec

    try:
        spec = _flat_args_to_spec(args)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"spec validation failed: {exc}") from exc

    runner = _get_job_runner()
    job = runner.enqueue_generate(design_id=state.design_id, spec=spec)
    background_tasks.add_task(runner.run_queued_job, job.id, spec)
    state.current_spec = spec
    chat_service._save_state(state)

    return {
        "status": "started",
        "job_id": job.id,
        "design_id": job.design_id,
        "version_no": job.version_no,
    }


async def _tool_modify(state, args: dict, background_tasks: BackgroundTasks):
    from services.api.app.routers.designs import _get_job_runner
    from services.api.app.services.chat_service import _flat_args_to_spec
    from services.api.app.services.spec_patch import apply_patch

    if state.current_spec is None:
        raise HTTPException(status_code=400, detail="no current design to modify")

    changes = args.get("changes", [])
    if not changes:
        raise HTTPException(status_code=400, detail="changes array is required")

    try:
        patched = apply_patch(state.current_spec, changes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    runner = _get_job_runner()
    job = runner.enqueue_generate(design_id=state.design_id, spec=patched)
    background_tasks.add_task(runner.run_queued_job, job.id, patched)
    state.current_spec = patched
    chat_service._save_state(state)

    return {
        "status": "started",
        "job_id": job.id,
        "design_id": job.design_id,
        "version_no": job.version_no,
    }


async def _tool_modify_selected(state, args: dict, background_tasks: BackgroundTasks):
    from services.api.app.routers.designs import _get_job_runner
    from services.api.app.services.selected_part_modifier import apply_selected_part_modification

    if state.current_spec is None:
        raise HTTPException(status_code=400, detail="no current design to modify")

    try:
        patched = apply_selected_part_modification(
            state.current_spec,
            args.get("part_ref", ""),
            args.get("operation", ""),
            args.get("value"),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    runner = _get_job_runner()
    job = runner.enqueue_generate(design_id=state.design_id, spec=patched)
    background_tasks.add_task(runner.run_queued_job, job.id, patched)
    state.current_spec = patched
    chat_service._save_state(state)

    return {
        "status": "started",
        "job_id": job.id,
        "design_id": job.design_id,
        "version_no": job.version_no,
    }
