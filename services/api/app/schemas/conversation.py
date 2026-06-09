"""Pydantic models for the conversations CRUD endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    design_id: str


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]


class ConversationDetail(BaseModel):
    conversation_id: str
    design_id: str | None
    messages: list[dict]
    current_spec: dict | None
    selected_refs: list[str]


class ConversationCreateRequest(BaseModel):
    conversation_id: str | None = Field(default=None, min_length=1)


class ConversationRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)
