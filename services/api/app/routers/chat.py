from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.api.app.graph.design_graph import run_shadow_classification
from services.api.app.graph.design_graph import classify_message_intent
from services.api.app.graph.mode import get_graph_mode
from services.api.app.graph.sse_adapter import convert_sse_events
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
    """Partial mode: run LangGraph partial graph, fallback to legacy on error."""
    import logging
    logger = logging.getLogger(__name__)

    try:
        from services.api.app.routers.designs import _get_job_runner

        job_runner = _get_job_runner()
        state = chat_service.get_or_create_state(req.conversation_id)

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
            "current_spec": state.current_spec if hasattr(state, "current_spec") else None,
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
                # Yield a final message event with the graph result
                import json
                msg = json.dumps({
                    "intent": result.get("intent", "unknown"),
                    "job_id": result.get("job_id", ""),
                    "status": result.get("status", ""),
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
