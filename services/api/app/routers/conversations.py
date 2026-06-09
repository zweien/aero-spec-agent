"""CRUD router for conversations, backed by ConversationIndex."""

from __future__ import annotations

import shutil
import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException

from services.api.app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationDetail,
    ConversationListResponse,
    ConversationRenameRequest,
    ConversationSummary,
)

if TYPE_CHECKING:
    from services.api.app.services.chat_service import ChatService
    from services.api.app.services.conversation_index import ConversationIndex

router = APIRouter(prefix="/api/conversations", tags=["conversations"])
_chat_service: ChatService | None = None
_index: ConversationIndex | None = None


def init(chat_service: ChatService, index: ConversationIndex) -> None:
    """Wire in the ChatService and ConversationIndex singletons."""
    global _chat_service, _index
    _chat_service = chat_service
    _index = index


def _require_services():
    if _chat_service is None or _index is None:
        raise RuntimeError("conversations router not initialized — call init() first")
    return _chat_service, _index


@router.get("", response_model=ConversationListResponse)
def list_conversations():
    _, index = _require_services()
    entries = index.list_entries()
    for e in entries:
        if e.get("title") is None:
            e["title"] = "新对话"
    return ConversationListResponse(conversations=entries)


@router.post("", response_model=ConversationDetail)
def create_conversation(req: ConversationCreateRequest | None = None):
    chat_svc, index = _require_services()
    conversation_id = req.conversation_id if req and req.conversation_id else str(uuid.uuid4())
    state = chat_svc.get_or_create_state(conversation_id)
    chat_svc._save_state(state)
    index.update_entry(
        conversation_id,
        title="",
        message_count=len(state.messages),
        design_id=state.design_id,
    )
    return ConversationDetail(
        conversation_id=state.conversation_id,
        design_id=state.design_id,
        messages=state.messages,
        current_spec=(
            state.current_spec.model_dump(mode="json") if state.current_spec else None
        ),
        selected_refs=state.selected_refs,
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str):
    chat_svc, index = _require_services()
    state_path = chat_svc._state_path(conversation_id)
    in_memory = conversation_id in chat_svc._conversations
    if not state_path.exists() and not in_memory:
        raise HTTPException(status_code=404, detail="conversation not found")
    state = chat_svc.get_or_create_state(conversation_id)
    return ConversationDetail(
        conversation_id=state.conversation_id,
        design_id=state.design_id,
        messages=state.messages,
        current_spec=(
            state.current_spec.model_dump(mode="json") if state.current_spec else None
        ),
        selected_refs=state.selected_refs,
    )


@router.patch("/{conversation_id}", response_model=ConversationSummary)
def rename_conversation(conversation_id: str, req: ConversationRenameRequest):
    _, index = _require_services()
    entry = index.get_entry(conversation_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="conversation not found in index")
    index.update_entry(conversation_id, title=req.title)
    updated = index.get_entry(conversation_id)
    return updated  # type: ignore[return-value]


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str):
    chat_svc, index = _require_services()
    entry = index.get_entry(conversation_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="conversation not found in index")
    state_dir = chat_svc._state_path(conversation_id).parent
    if state_dir.exists():
        shutil.rmtree(state_dir)
    chat_svc._conversations.pop(conversation_id, None)
    index.remove_entry(conversation_id)
