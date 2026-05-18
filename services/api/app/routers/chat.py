from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.api.app.graph.design_graph import run_shadow_classification
from services.api.app.graph.nodes.classify_intent import _classify as langgraph_classify
from services.api.app.graph.design_graph import classify_message_intent
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
    """Run old and new paths in parallel. Stream old path to user, log divergence."""
    # Old path intent
    state = chat_service.get_or_create_state(req.conversation_id)
    old_intent = classify_message_intent(
        req.message,
        selected_refs=req.selected_refs or None,
        has_current_spec=state.current_spec is not None,
    )

    # New path (LangGraph)
    new_result = run_shadow_classification(
        req.message,
        selected_refs=req.selected_refs or None,
        has_current_spec=state.current_spec is not None,
    )

    # Log divergence
    shadow_logger.log_divergence(
        conversation_id=req.conversation_id,
        user_message=req.message,
        old_result={"intent": old_intent},
        new_result={"intent": new_result["intent"], "tool_name": new_result.get("tool_name")},
    )

    # Stream old path to user (unchanged behavior)
    return StreamingResponse(
        chat_service.chat_stream(
            conversation_id=req.conversation_id,
            message=req.message,
            selected_refs=req.selected_refs,
            background_tasks=background_tasks,
        ),
        media_type="text/event-stream",
    )
