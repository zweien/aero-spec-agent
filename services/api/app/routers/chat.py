from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.api.app.services.chat_service import ChatService

router = APIRouter(prefix="/api", tags=["chat"])
chat_service = ChatService()


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
