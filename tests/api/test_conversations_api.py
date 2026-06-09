"""Tests for the conversations CRUD router."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.api.app.main import app
from services.api.app.services.chat_service import ChatService
from services.api.app.services.conversation_index import ConversationIndex


@pytest.fixture()
def client(tmp_path: Path):
    """Create a TestClient with fresh ChatService and ConversationIndex."""
    chat_svc = ChatService(storage_root=tmp_path)
    idx = ConversationIndex(root=tmp_path)
    idx.bootstrap()

    from services.api.app.routers import conversations as conv_mod

    conv_mod.init(chat_svc, idx)

    app.dependency_overrides.clear()
    # Re-register the router to pick up the new singletons.
    # Since the router module is already included via main.py,
    # we just need to make sure init() was called (done above).
    return TestClient(app)


def test_list_empty(client: TestClient):
    response = client.get("/api/conversations")
    assert response.status_code == 200
    data = response.json()
    assert data["conversations"] == []


def test_create_conversation(client: TestClient):
    response = client.post("/api/conversations", json={})
    assert response.status_code == 200
    data = response.json()
    assert "conversation_id" in data
    assert data["messages"] == []

    # Should appear in list
    list_resp = client.get("/api/conversations")
    assert list_resp.status_code == 200
    convs = list_resp.json()["conversations"]
    assert len(convs) == 1
    assert convs[0]["conversation_id"] == data["conversation_id"]


def test_create_with_custom_id(client: TestClient):
    response = client.post(
        "/api/conversations", json={"conversation_id": "my-custom-id"}
    )
    assert response.status_code == 200
    assert response.json()["conversation_id"] == "my-custom-id"


def test_get_conversation_detail(client: TestClient, tmp_path: Path):
    # Create a conversation first
    chat_svc = ChatService(storage_root=tmp_path)
    state = chat_svc.get_or_create_state("conv-detail-1")
    state.messages.append({"role": "user", "content": "hello"})
    chat_svc._save_state(state)

    # Also update the index (the router's init already did this for the
    # module-level singletons, but we need to update the one used by client)
    from services.api.app.routers import conversations as conv_mod

    idx = conv_mod._index
    idx.update_entry(
        "conv-detail-1",
        title="hello",
        message_count=len(state.messages),
        design_id=state.design_id,
    )

    response = client.get("/api/conversations/conv-detail-1")
    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == "conv-detail-1"
    assert len(data["messages"]) == 1


def test_get_nonexistent_conversation(client: TestClient):
    response = client.get("/api/conversations/no-such-conv")
    assert response.status_code == 404


def test_rename_conversation(client: TestClient):
    # Create first
    create_resp = client.post(
        "/api/conversations", json={"conversation_id": "rename-me"}
    )
    assert create_resp.status_code == 200

    # Rename
    rename_resp = client.patch(
        "/api/conversations/rename-me", json={"title": "New Title"}
    )
    assert rename_resp.status_code == 200
    assert rename_resp.json()["title"] == "New Title"

    # Verify in list
    list_resp = client.get("/api/conversations")
    convs = list_resp.json()["conversations"]
    entry = next(c for c in convs if c["conversation_id"] == "rename-me")
    assert entry["title"] == "New Title"


def test_delete_conversation(client: TestClient, tmp_path: Path):
    # Create
    create_resp = client.post(
        "/api/conversations", json={"conversation_id": "delete-me"}
    )
    assert create_resp.status_code == 200

    # Verify directory exists
    conv_dir = tmp_path / "conversations" / "delete-me"
    assert conv_dir.exists()

    # Delete
    del_resp = client.delete("/api/conversations/delete-me")
    assert del_resp.status_code == 204

    # Verify removed from index
    list_resp = client.get("/api/conversations")
    convs = list_resp.json()["conversations"]
    ids = [c["conversation_id"] for c in convs]
    assert "delete-me" not in ids

    # Verify directory gone
    assert not conv_dir.exists()
