from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from services.api.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_chat_endpoint_returns_sse_content_type(client):
    with patch("services.api.app.routers.chat.chat_service") as mock_svc:
        async def fake_stream(*args, **kwargs):
            yield 'event: message\ndata: {"content": "hello"}\n\n'

        mock_svc.chat_stream = fake_stream
        response = client.post(
            "/api/chat",
            json={"conversation_id": "test-conv", "message": "hello"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]


def test_chat_endpoint_forwards_selected_refs(client):
    captured = {}

    with patch("services.api.app.routers.chat.chat_service") as mock_svc:
        async def fake_stream(*, conversation_id, message, selected_refs, background_tasks):
            captured["conversation_id"] = conversation_id
            captured["message"] = message
            captured["selected_refs"] = selected_refs
            captured["background_tasks"] = background_tasks
            yield 'event: message\ndata: {"content": "ok"}\n\n'

        mock_svc.chat_stream = fake_stream
        response = client.post(
            "/api/chat",
            json={
                "conversation_id": "test-conv",
                "message": "hello",
                "selected_refs": ["part:right_engine"],
            },
        )

    assert response.status_code == 200
    assert captured["conversation_id"] == "test-conv"
    assert captured["message"] == "hello"
    assert captured["selected_refs"] == ["part:right_engine"]
    assert captured["background_tasks"] is not None


def test_chat_endpoint_rejects_empty_message(client):
    response = client.post(
        "/api/chat",
        json={"conversation_id": "test-conv", "message": ""},
    )
    assert response.status_code == 422


def test_chat_endpoint_rejects_missing_conversation_id(client):
    response = client.post(
        "/api/chat",
        json={"message": "hello"},
    )
    assert response.status_code == 422
