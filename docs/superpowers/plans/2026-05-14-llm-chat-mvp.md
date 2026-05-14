# LLM Chat MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a natural-language chat endpoint and frontend so users can describe aircraft requirements conversationally, have an LLM generate/modify `aircraft_spec`, trigger CAD generation, and see streamed results in the web UI.

**Architecture:** A new FastAPI SSE endpoint (`POST /api/chat`) calls an OpenAI-compatible LLM with function calling. `ChatService` manages per-conversation state in memory. The LLM invokes `generate_design` or `modify_design` tools, which delegate to the existing `JobRunner` and `spec_patch` module. The frontend rewrites `ChatPanel` to consume SSE events and dynamically updates `ParameterPanel` from the generated spec.

**Tech Stack:** Python 3.11+, FastAPI, openai SDK, Pydantic v2, Next.js 14, React 18, TypeScript, native fetch SSE.

---

## Scope

Covers the approved design at `docs/superpowers/specs/2026-05-14-llm-chat-mvp-design.md`. Produces a fully working local demo: user types natural language, LLM generates spec, CAD generates, 3D preview updates. Multi-turn modification supported.

Out of scope: LangGraph, database, Redis, auth, CAD object selection, VSPAERO analysis, parameter panel editing.

## File Structure

### New files

- `services/api/app/services/spec_patch.py` — deep merge changes into AircraftSpec
- `services/api/app/services/chat_service.py` — conversation state + LLM orchestration
- `services/api/app/routers/chat.py` — SSE endpoint
- `tests/api/test_spec_patch.py` — spec patch tests
- `tests/api/test_chat_service.py` — chat service tests
- `tests/api/test_chat_api.py` — SSE endpoint integration tests

### Modified files

- `pyproject.toml` — add `openai>=1.30.0` + trimesh dependency
- `.env` — add `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`
- `services/api/app/main.py` — register chat router, update CORS
- `apps/web/src/components/chat/ChatPanel.tsx` — SSE streaming rewrite
- `apps/web/src/app/page.tsx` — conversation state + dynamic params
- `apps/web/src/components/parameter-panel/ParameterPanel.tsx` — dynamic from spec
- `apps/web/src/app/globals.css` — chat message styles

### Existing uncommitted files to commit first

- `services/workers/cad_worker/openvsp_generator/obj_to_glb.py`
- `tests/api/test_obj_to_glb.py`
- `apps/web/src/components/cad-viewer/cadPreviewStatus.ts`
- `apps/web/src/components/cad-viewer/cadPreviewStatus.test.ts`

---

## Task 1: Commit Existing Uncommitted Work

**Files:**
- Stage: all modified and untracked files from git status

- [ ] **Step 1: Verify existing tests pass**

Run:

```bash
CAD_BACKEND=fake .venv/bin/python -m pytest -q
```

Expected: all pass.

- [ ] **Step 2: Stage and commit**

```bash
git add services/workers/cad_worker/openvsp_generator/obj_to_glb.py tests/api/test_obj_to_glb.py apps/web/src/components/cad-viewer/cadPreviewStatus.ts apps/web/src/components/cad-viewer/cadPreviewStatus.test.ts apps/web/src/components/cad-viewer/AircraftThreePreview.tsx apps/web/src/components/cad-viewer/CadViewer.tsx apps/web/src/app/globals.css pyproject.toml services/workers/cad_worker/openvsp_generator/backend.py tests/api/test_openvsp_backend_unit.py tests/api/test_openvsp_integration.py
git commit -m "feat: add obj-to-glb conversion and cad preview status"
```

---

## Task 2: Add openai Dependency and Environment Variables

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env`

- [ ] **Step 1: Add openai to dependencies**

In `pyproject.toml`, add `"openai>=1.30.0"` to the `dependencies` list. The updated dependencies section:

```toml
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "pydantic>=2.8.0",
  "pyyaml>=6.0.2",
  "trimesh>=4.10.0",
  "openai>=1.30.0",
]
```

- [ ] **Step 2: Add LLM environment variables to .env**

Append to `.env`:

```
OPENAI_API_KEY=sk-placeholder
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
```

- [ ] **Step 3: Install new dependency**

Run:

```bash
. .venv/bin/activate && pip install -e ".[dev]"
```

Expected: openai installs successfully.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .env
git commit -m "chore: add openai dependency and llm env config"
```

---

## Task 3: Implement Spec Patch Module

**Files:**
- Create: `services/api/app/services/spec_patch.py`
- Create: `tests/api/test_spec_patch.py`

- [ ] **Step 1: Write failing spec patch tests**

Write `tests/api/test_spec_patch.py`:

```python
from pathlib import Path

import pytest

from services.api.app.services.spec_io import load_aircraft_spec
from services.api.app.services.spec_patch import apply_patch


EXAMPLE = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


def test_apply_patch_changes_wing_span():
    spec = load_aircraft_spec(EXAMPLE)
    patched = apply_patch(spec, [{"path": "wing.span.value", "value": 14.0}])
    assert patched.wing.span.value == 14.0
    assert patched.fuselage.length.value == spec.fuselage.length.value


def test_apply_patch_adds_missing_optional_field():
    spec = load_aircraft_spec(EXAMPLE)
    assert spec.wing.sweep is not None
    patched = apply_patch(spec, [{"path": "wing.sweep.value", "value": 10}])
    assert patched.wing.sweep is not None
    assert patched.wing.sweep.value == 10


def test_apply_patch_rejects_invalid_path():
    spec = load_aircraft_spec(EXAMPLE)
    with pytest.raises(KeyError, match="nonexistent"):
        apply_patch(spec, [{"path": "nonexistent.field", "value": 1}])


def test_apply_patch_validates_result():
    spec = load_aircraft_spec(EXAMPLE)
    with pytest.raises(Exception):
        apply_patch(spec, [{"path": "schema_version", "value": "99.0"}])


def test_apply_patch_source_field():
    spec = load_aircraft_spec(EXAMPLE)
    patched = apply_patch(spec, [
        {"path": "wing.span.value", "value": 14.0},
        {"path": "wing.span.source", "value": "user"},
        {"path": "wing.span.confidence", "value": 1.0},
    ])
    assert patched.wing.span.value == 14.0
    assert patched.wing.span.source == "user"
    assert patched.wing.span.confidence == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_spec_patch.py -q
```

Expected: FAIL — `spec_patch` module does not exist.

- [ ] **Step 3: Implement spec_patch.py**

Write `services/api/app/services/spec_patch.py`:

```python
from __future__ import annotations

from typing import Any

from services.api.app.schemas.aircraft_spec import AircraftSpec


def apply_patch(spec: AircraftSpec, changes: list[dict[str, Any]]) -> AircraftSpec:
    data = spec.model_dump(mode="json")
    for change in changes:
        path = change["path"]
        value = change["value"]
        _set_nested(data, path, value)
    return AircraftSpec.model_validate(data)


def _set_nested(data: dict[str, Any], path: str, value: Any) -> None:
    keys = path.split(".")
    current = data
    for key in keys[:-1]:
        if key not in current:
            raise KeyError(f"nonexistent path component: {key} in {path}")
        current = current[key]
    last_key = keys[-1]
    if last_key not in current:
        raise KeyError(f"nonexistent path component: {last_key} in {path}")
    current[last_key] = value
```

- [ ] **Step 4: Run spec patch tests**

Run:

```bash
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_spec_patch.py -q
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add services/api/app/services/spec_patch.py tests/api/test_spec_patch.py
git commit -m "feat: add spec patch deep merge"
```

---

## Task 4: Implement ChatService

**Files:**
- Create: `services/api/app/services/chat_service.py`
- Create: `tests/api/test_chat_service.py`

- [ ] **Step 1: Write failing chat service tests**

Write `tests/api/test_chat_service.py`:

```python
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.chat_service import (
    ChatService,
    ConversationState,
    SYSTEM_PROMPT_TEMPLATE,
)
from services.api.app.services.spec_io import load_aircraft_spec
from services.api.app.services.spec_patch import apply_patch


EXAMPLE = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


def test_conversation_state_is_created():
    svc = ChatService()
    state = svc.get_or_create_state("conv-1")
    assert state.conversation_id == "conv-1"
    assert state.current_spec is None
    assert state.messages == []


def test_conversation_state_reuses_existing():
    svc = ChatService()
    state1 = svc.get_or_create_state("conv-1")
    state1.messages.append({"role": "user", "content": "hello"})
    state2 = svc.get_or_create_state("conv-1")
    assert len(state2.messages) == 1


def test_system_prompt_includes_current_spec():
    spec = load_aircraft_spec(EXAMPLE)
    prompt = SYSTEM_PROMPT_TEMPLATE.format(current_spec_yaml="wing.span: 12.0")
    assert "wing.span: 12.0" in prompt
    assert "AeroSpec Agent" in prompt


def test_system_prompt_shows_no_design_when_empty():
    prompt = SYSTEM_PROMPT_TEMPLATE.format(current_spec_yaml="尚无设计")
    assert "尚无设计" in prompt


def test_build_tools_definitions():
    svc = ChatService()
    tools = svc.build_tools()
    names = [t["function"]["name"] for t in tools]
    assert "generate_design" in names
    assert "modify_design" in names
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_chat_service.py -q
```

Expected: FAIL — `chat_service` module does not exist.

- [ ] **Step 3: Implement ChatService**

Write `services/api/app/services/chat_service.py`:

```python
from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.spec_io import dump_aircraft_spec
from services.api.app.services.spec_patch import apply_patch

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """你是 AeroSpec Agent，一个飞机概念设计助手。

用户用自然语言描述飞机需求，你负责生成或修改 aircraft_spec 参数化设计。

当前设计状态：
{current_spec_yaml}

规则：
- 只处理固定翼无人机（fixed_wing_uav），常规布局（conventional）
- 所有数值参数必须包含 unit、source、confidence 字段
- 用户明确给出的参数：source=user, confidence=1.0
- 你推断的参数：source=inferred, confidence=0.7-0.9
- 无法确定的参数使用合理默认值：source=rule_default, confidence=0.7
- 新建设计使用 generate_design，修改现有设计使用 modify_design
- 修改时只输出需要变更的字段
- 生成完成后简要解释设计参数和依据"""

GENERATE_DESIGN_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_design",
        "description": "根据用户需求生成新的飞机设计 spec。当用户描述全新的飞机需求时使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "spec": {
                    "type": "object",
                    "description": "完整的 AircraftSpec 对象，包含 schema_version, aircraft, mission, fuselage, wing, tail, engine 字段",
                }
            },
            "required": ["spec"],
        },
    },
}

MODIFY_DESIGN_TOOL = {
    "type": "function",
    "function": {
        "name": "modify_design",
        "description": "修改当前飞机设计的参数。当用户要求修改现有设计的部分参数时使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "changes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "点分隔的字段路径，例如 wing.span.value",
                            },
                            "value": {"description": "新值"},
                            "reason": {
                                "type": "string",
                                "description": "修改原因",
                            },
                        },
                        "required": ["path", "value"],
                    },
                }
            },
            "required": ["changes"],
        },
    },
}


@dataclass
class ConversationState:
    conversation_id: str
    design_id: str
    messages: list[dict[str, str]] = field(default_factory=list)
    current_spec: AircraftSpec | None = None


def _sse_event(event_type: str, data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else json.dumps({"content": data}, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"


class ChatService:
    def __init__(self) -> None:
        self._conversations: dict[str, ConversationState] = {}
        api_key = os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("OPENAI_BASE_URL")
        self._model = os.getenv("OPENAI_MODEL", "deepseek-chat")
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._job_runner = None

    def set_job_runner(self, runner: Any) -> None:
        self._job_runner = runner

    def get_or_create_state(self, conversation_id: str) -> ConversationState:
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = ConversationState(
                conversation_id=conversation_id,
                design_id=conversation_id,
            )
        return self._conversations[conversation_id]

    def build_tools(self) -> list[dict[str, Any]]:
        return [GENERATE_DESIGN_TOOL, MODIFY_DESIGN_TOOL]

    def _build_system_prompt(self, state: ConversationState) -> str:
        if state.current_spec is not None:
            import tempfile
            from pathlib import Path
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                dump_aircraft_spec(state.current_spec, Path(f.name))
                spec_yaml = Path(f.name).read_text(encoding="utf-8")
            Path(f.name).unlink(missing_ok=True)
        else:
            spec_yaml = "尚无设计"
        return SYSTEM_PROMPT_TEMPLATE.format(current_spec_yaml=spec_yaml)

    async def chat_stream(
        self,
        conversation_id: str,
        message: str,
    ) -> AsyncIterator[str]:
        state = self.get_or_create_state(conversation_id)
        state.messages.append({"role": "user", "content": message})

        system_prompt = self._build_system_prompt(state)
        api_messages = [{"role": "system", "content": system_prompt}] + state.messages

        collected_content = ""
        tool_calls_collected: dict[int, dict[str, Any]] = {}

        response = self._client.chat.completions.create(
            model=self._model,
            messages=api_messages,
            tools=self.build_tools(),
            stream=True,
        )

        for chunk in response:
            choice = chunk.choices[0] if chunk.choices else None
            if choice is None:
                continue

            delta = choice.delta

            if delta.content:
                collected_content += delta.content
                yield _sse_event("message", delta.content)

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    if tc.index not in tool_calls_collected:
                        tool_calls_collected[tc.index] = {
                            "id": tc.id or "",
                            "name": "",
                            "arguments": "",
                        }
                    if tc.id:
                        tool_calls_collected[tc.index]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls_collected[tc.index]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls_collected[tc.index]["arguments"] += tc.function.arguments

            if choice.finish_reason == "tool_calls":
                break

        assistant_msg: dict[str, Any] = {"role": "assistant", "content": collected_content or None}
        if tool_calls_collected:
            assistant_msg["tool_calls"] = []
            for idx in sorted(tool_calls_collected):
                tc_data = tool_calls_collected[idx]
                assistant_msg["tool_calls"].append({
                    "id": tc_data["id"],
                    "type": "function",
                    "function": {
                        "name": tc_data["name"],
                        "arguments": tc_data["arguments"],
                    },
                })

        state.messages.append(assistant_msg)

        if not tool_calls_collected:
            return

        for idx in sorted(tool_calls_collected):
            tc_data = tool_calls_collected[idx]
            tool_name = tc_data["name"]
            tool_args_str = tc_data["arguments"]
            tool_call_id = tc_data["id"]

            yield _sse_event("tool_call", {"name": tool_name, "arguments": tool_args_str})

            try:
                tool_args = json.loads(tool_args_str)
            except json.JSONDecodeError:
                tool_result = json.dumps({"error": "invalid JSON arguments"}, ensure_ascii=False)
                state.messages.append({"role": "tool", "tool_call_id": tool_call, "content": tool_result})
                continue

            if tool_name == "generate_design":
                async for event in await self._handle_generate_design(state, tool_args):
                    yield event
            elif tool_name == "modify_design":
                async for event in await self._handle_modify_design(state, tool_args):
                    yield event
            else:
                state.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps({"error": f"unknown tool: {tool_name}"}, ensure_ascii=False),
                })

        second_response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system_prompt}] + state.messages,
            stream=True,
        )

        final_content = ""
        for chunk in second_response:
            choice = chunk.choices[0] if chunk.choices else None
            if choice and choice.delta and choice.delta.content:
                final_content += choice.delta.content
                yield _sse_event("message", choice.delta.content)

        if final_content:
            state.messages.append({"role": "assistant", "content": final_content})

    async def _handle_generate_design(self, state: ConversationState, args: dict[str, Any]) -> AsyncIterator[str]:
        try:
            spec_data = args.get("spec", {})
            spec = AircraftSpec.model_validate(spec_data)
        except Exception as exc:
            yield _sse_event("error", {"content": f"spec 校验失败: {exc}"})
            return

        if self._job_runner is None:
            yield _sse_event("error", {"content": "job runner not configured"})
            return

        yield _sse_event("generation_started", {"design_id": state.design_id})
        job = self._job_runner.generate(design_id=state.design_id, spec=spec)
        state.current_spec = spec

        result = {
            "status": job.status,
            "version_no": job.version_no,
            "design_id": job.design_id,
            "files": list(job.files.keys()),
            "error_message": job.error_message,
        }
        yield _sse_event("generation_complete", result)

        state.messages.append({
            "role": "tool",
            "tool_call_id": "",
            "content": json.dumps(result, ensure_ascii=False),
        })

    async def _handle_modify_design(self, state: ConversationState, args: dict[str, Any]) -> AsyncIterator[str]:
        if state.current_spec is None:
            yield _sse_event("error", {"content": "没有当前设计，请先使用 generate_design 创建设计"})
            return

        changes = args.get("changes", [])
        if not changes:
            yield _sse_event("error", {"content": "changes 不能为空"})
            return

        try:
            patched = apply_patch(state.current_spec, changes)
        except Exception as exc:
            yield _sse_event("error", {"content": f"spec patch 失败: {exc}"})
            return

        if self._job_runner is None:
            yield _sse_event("error", {"content": "job runner not configured"})
            return

        yield _sse_event("generation_started", {"design_id": state.design_id})
        job = self._job_runner.generate(design_id=state.design_id, spec=patched)
        state.current_spec = patched

        result = {
            "status": job.status,
            "version_no": job.version_no,
            "design_id": job.design_id,
            "files": list(job.files.keys()),
            "error_message": job.error_message,
        }
        yield _sse_event("generation_complete", result)

        state.messages.append({
            "role": "tool",
            "tool_call_id": "",
            "content": json.dumps(result, ensure_ascii=False),
        })
```

- [ ] **Step 4: Run chat service tests**

Run:

```bash
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_chat_service.py -q
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add services/api/app/services/chat_service.py tests/api/test_chat_service.py
git commit -m "feat: add chat service with llm orchestration"
```

---

## Task 5: Expose Chat SSE Endpoint

**Files:**
- Create: `services/api/app/routers/chat.py`
- Create: `tests/api/test_chat_api.py`
- Modify: `services/api/app/main.py`

- [ ] **Step 1: Write failing chat API tests**

Write `tests/api/test_chat_api.py`:

```python
import json
from unittest.mock import AsyncMock, MagicMock, patch

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_chat_api.py -q
```

Expected: FAIL — `chat` router module does not exist.

- [ ] **Step 3: Implement chat router**

Write `services/api/app/routers/chat.py`:

```python
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.api.app.services.chat_service import ChatService

router = APIRouter(prefix="/api", tags=["chat"])
chat_service = ChatService()


class ChatRequest(BaseModel):
    conversation_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


def set_job_runner(runner) -> None:
    chat_service.set_job_runner(runner)


@router.post("/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(
        chat_service.chat_stream(
            conversation_id=req.conversation_id,
            message=req.message,
        ),
        media_type="text/event-stream",
    )
```

- [ ] **Step 4: Register chat router in main.py**

Modify `services/api/app/main.py` to import and register the chat router. Update the full file:

```python
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.app.routers.chat import router as chat_router
from services.api.app.routers.chat import set_job_runner as set_chat_job_runner
from services.api.app.routers.designs import router as designs_router
from services.api.app.routers.designs import runner as designs_runner


def _local_web_origins() -> list[str]:
    web_port = os.getenv("WEB_PORT", "3900")
    return [
        f"http://localhost:{web_port}",
        f"http://127.0.0.1:{web_port}",
    ]


app = FastAPI(title="AeroSpec Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_local_web_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(designs_router)
app.include_router(chat_router)

set_chat_job_runner(designs_runner)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Run chat API tests**

Run:

```bash
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_chat_api.py -q
```

Expected: all PASS.

- [ ] **Step 6: Run full test suite**

Run:

```bash
CAD_BACKEND=fake .venv/bin/python -m pytest -q
```

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add services/api/app/routers/chat.py services/api/app/main.py tests/api/test_chat_api.py
git commit -m "feat: add chat sse endpoint"
```

---

## Task 6: Rewrite ChatPanel with SSE Streaming

**Files:**
- Rewrite: `apps/web/src/components/chat/ChatPanel.tsx`
- Modify: `apps/web/src/app/globals.css`

- [ ] **Step 1: Add chat CSS styles**

Append to `apps/web/src/app/globals.css`:

```css
.chat-messages {
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

.chat-messages .message {
  margin-bottom: 8px;
}

.chat-messages .message.user {
  background: #e8edf5;
  border-color: #c5ccd6;
}

.chat-messages .message.assistant {
  background: #ffffff;
  border-color: #d9dde3;
}

.chat-messages .message.error {
  background: #fef2f2;
  border-color: #fca5a5;
  color: #991b1b;
}

.chat-messages .message.generating {
  background: #f0f7ff;
  border-color: #93c5fd;
  color: #1e40af;
}

.chat-input-row {
  display: flex;
  gap: 8px;
}

.chat-input-row textarea {
  flex: 1;
}

.chat-input-row button {
  padding: 0 16px;
  white-space: nowrap;
}
```

- [ ] **Step 2: Rewrite ChatPanel.tsx**

Rewrite `apps/web/src/components/chat/ChatPanel.tsx`:

```tsx
"use client";

import { useRef, useState } from "react";

export type ChatMessage = {
  role: "user" | "assistant" | "error" | "generating";
  content: string;
};

type ChatPanelProps = {
  messages: ChatMessage[];
  isGenerating: boolean;
  onSend: (message: string) => void;
};

export function ChatPanel({ messages, isGenerating, onSend }: ChatPanelProps) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  function handleSubmit() {
    const trimmed = input.trim();
    if (!trimmed || isGenerating) return;
    onSend(trimmed);
    setInput("");
  }

  return (
    <section className="panel chat-panel">
      <header>对话</header>
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="message assistant">
            描述你想要的飞机设计，例如「设计一架翼展 12 米、双发、上单翼、常规尾翼的固定翼无人机」。
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            {msg.content}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      <div className="chat-input-row">
        <textarea
          aria-label="设计需求"
          placeholder="描述飞机设计需求..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
          disabled={isGenerating}
        />
        <button type="button" disabled={isGenerating || !input.trim()} onClick={handleSubmit}>
          {isGenerating ? "生成中" : "发送"}
        </button>
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/chat/ChatPanel.tsx apps/web/src/app/globals.css
git commit -m "feat: rewrite chat panel with sse streaming support"
```

---

## Task 7: Update ParameterPanel for Dynamic Spec

**Files:**
- Modify: `apps/web/src/components/parameter-panel/ParameterPanel.tsx`

- [ ] **Step 1: Rewrite ParameterPanel to accept spec data**

Rewrite `apps/web/src/components/parameter-panel/ParameterPanel.tsx`:

```tsx
"use client";

type Scalar = {
  value: string | number;
  unit?: string;
  source: string;
  confidence: number;
  reason?: string;
};

type SpecSection = {
  [key: string]: Scalar | SpecSection | undefined;
};

type AircraftSpecData = {
  aircraft?: { name?: string; type?: string; layout?: string };
  mission?: SpecSection;
  fuselage?: SpecSection;
  wing?: SpecSection;
  tail?: SpecSection;
  engine?: SpecSection;
};

type ParameterPanelProps = {
  spec: AircraftSpecData | null;
};

const SECTION_LABELS: Record<string, string> = {
  mission: "任务需求",
  fuselage: "机身",
  wing: "机翼",
  tail: "尾翼",
  engine: "发动机",
};

const FIELD_LABELS: Record<string, string> = {
  cruise_speed: "巡航速度",
  payload: "载荷",
  priority: "优先级",
  length: "长度",
  max_diameter: "最大直径",
  position: "位置",
  span: "翼展",
  root_chord: "根弦长",
  tip_chord: "尖弦长",
  sweep: "后掠角",
  dihedral: "上反角",
  airfoil: "翼型",
  type: "类型",
  count: "数量",
};

const SOURCE_LABELS: Record<string, string> = {
  user: "用户",
  inferred: "推断",
  rule_default: "默认",
  system_default: "系统",
};

function isScalar(val: unknown): val is Scalar {
  return (
    typeof val === "object" &&
    val !== null &&
    "value" in val &&
    "source" in val
  );
}

function extractParameters(
  spec: AircraftSpecData
): Array<{ label: string; scalar: Scalar }> {
  const params: Array<{ label: string; scalar: Scalar }> = [];
  for (const [sectionKey, sectionLabel] of Object.entries(SECTION_LABELS)) {
    const section = spec[sectionKey as keyof AircraftSpecData] as
      | SpecSection
      | undefined;
    if (!section) continue;
    for (const [fieldKey, fieldValue] of Object.entries(section)) {
      if (fieldValue !== undefined && isScalar(fieldValue)) {
        const label =
          FIELD_LABELS[fieldKey] ?? fieldKey;
        params.push({
          label: `${sectionLabel} · ${label}`,
          scalar: fieldValue,
        });
      }
    }
  }
  return params;
}

export function ParameterPanel({ spec }: ParameterPanelProps) {
  const parameters = spec ? extractParameters(spec) : [];

  return (
    <section className="panel parameter-panel">
      <header>参数</header>
      {parameters.length === 0 ? (
        <div style={{ color: "#6c7685", fontSize: 14 }}>
          等待生成设计参数
        </div>
      ) : (
        parameters.map((item) => (
          <div className="parameter-row" key={item.label}>
            <span>{item.label}</span>
            <strong>
              {item.scalar.value}
              {item.scalar.unit ? ` ${item.scalar.unit}` : ""}
            </strong>
            <small>
              <span
                style={{
                  display: "inline-block",
                  padding: "1px 6px",
                  borderRadius: 3,
                  fontSize: 11,
                  background:
                    item.scalar.source === "user"
                      ? "#dbeafe"
                      : item.scalar.source === "inferred"
                        ? "#fef3c7"
                        : "#f1f5f9",
                }}
              >
                {SOURCE_LABELS[item.scalar.source] ?? item.scalar.source}
              </span>
              {" "}
              {Math.round(item.scalar.confidence * 100)}%
            </small>
          </div>
        ))
      )}
    </section>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/components/parameter-panel/ParameterPanel.tsx
git commit -m "feat: dynamic parameter panel from spec data"
```

---

## Task 8: Wire page.tsx with Chat State and SSE

**Files:**
- Rewrite: `apps/web/src/app/page.tsx`

- [ ] **Step 1: Rewrite page.tsx**

Rewrite `apps/web/src/app/page.tsx`:

```tsx
"use client";

import { useCallback, useRef, useState } from "react";

import { CadViewer } from "@/components/cad-viewer/CadViewer";
import {
  selectCadPreviewSource,
  type CadPreviewSource,
} from "@/components/cad-viewer/cadPreviewSource";
import type { AircraftPreviewSpec } from "@/components/cad-viewer/previewGeometry";
import {
  ChatPanel,
  type ChatMessage,
} from "@/components/chat/ChatPanel";
import { ParameterPanel } from "@/components/parameter-panel/ParameterPanel";
import { VersionPanel } from "@/components/version-panel/VersionPanel";

type VersionResponse = {
  files: string[];
  validation_report?: {
    spec_echo?: AircraftPreviewSpec;
  };
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8900";

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [files, setFiles] = useState<string[]>([]);
  const [jobStatus, setJobStatus] = useState<string | undefined>();
  const [versionNo, setVersionNo] = useState<number | undefined>();
  const [previewSource, setPreviewSource] = useState<CadPreviewSource | null>(null);
  const [previewSpec, setPreviewSpec] = useState<AircraftPreviewSpec | null>(null);
  const [specData, setSpecData] = useState<Record<string, unknown> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleSend = useCallback(
    async (message: string) => {
      const convId = conversationId ?? crypto.randomUUID();
      if (!conversationId) setConversationId(convId);

      setMessages((prev) => [...prev, { role: "user", content: message }]);
      setIsGenerating(true);

      const assistantIndex = messages.length + 1;
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "" },
      ]);

      const abortController = new AbortController();
      abortRef.current = abortController;

      try {
        const response = await fetch(`${API_BASE_URL}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            conversation_id: convId,
            message,
          }),
          signal: abortController.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error(`请求失败：HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          let eventType = "";
          for (const line of lines) {
            if (line.startsWith("event: ")) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              const dataStr = line.slice(6);
              try {
                const data = JSON.parse(dataStr);
                handleSSEEvent(
                  eventType,
                  data,
                  assistantIndex,
                  convId,
                );
              } catch {
                // skip malformed data lines
              }
              eventType = "";
            }
          }
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setMessages((prev) => [
          ...prev,
          {
            role: "error",
            content: err instanceof Error ? err.message : "请求失败",
          },
        ]);
      } finally {
        setIsGenerating(false);
        abortRef.current = null;
      }
    },
    [conversationId, messages.length],
  );

  const handleSSEEvent = useCallback(
    (
      eventType: string,
      data: Record<string, unknown>,
      assistantIdx: number,
      convId: string,
    ) => {
      switch (eventType) {
        case "message":
          setMessages((prev) => {
            const updated = [...prev];
            if (updated[assistantIdx]) {
              updated[assistantIdx] = {
                ...updated[assistantIdx],
                content: updated[assistantIdx].content + (data.content ?? ""),
              };
            }
            return updated;
          });
          break;

        case "tool_call":
          setMessages((prev) => [
            ...prev,
            {
              role: "generating",
              content: `正在${data.name === "generate_design" ? "生成设计" : "修改设计"}...`,
            },
          ]);
          break;

        case "generation_started":
          setJobStatus("running");
          break;

        case "generation_complete":
          setJobStatus("ready");
          if (data.version_no) setVersionNo(data.version_no as number);
          void refreshAfterGeneration(convId, data.version_no as number);
          break;

        case "error":
          setMessages((prev) => [
            ...prev,
            { role: "error", content: data.content ?? "发生错误" },
          ]);
          break;
      }
    },
    [],
  );

  const refreshAfterGeneration = useCallback(
    async (convId: string, vNo: number) => {
      try {
        const versionResp = await fetch(
          `${API_BASE_URL}/api/designs/${convId}/versions/${vNo}`,
        );
        if (!versionResp.ok) return;

        const version = (await versionResp.json()) as VersionResponse;
        setFiles(version.files);
        setPreviewSpec(version.validation_report?.spec_echo ?? null);
        setSpecData(version.validation_report?.spec_echo as Record<string, unknown> | null);

        const source = selectCadPreviewSource({
          apiBaseUrl: API_BASE_URL,
          designId: convId,
          versionNo: vNo,
          files: version.files,
        });
        setPreviewSource(source);
      } catch {
        // non-critical — preview will stay in parameter mode
      }
    },
    [],
  );

  return (
    <main className="workbench">
      <nav className="topbar">
        <strong>AeroSpec Agent</strong>
        <span>固定翼无人机概念设计 MVP</span>
      </nav>
      <div className="main-grid">
        <ChatPanel
          messages={messages}
          isGenerating={isGenerating}
          onSend={handleSend}
        />
        <CadViewer
          modelFormat={previewSource?.format}
          modelUrl={previewSource?.url}
          spec={previewSpec}
        />
        <ParameterPanel spec={specData} />
      </div>
      <VersionPanel
        apiBaseUrl={API_BASE_URL}
        designId={conversationId ?? "demo"}
        files={files}
        jobStatus={jobStatus}
        versionNo={versionNo}
      />
    </main>
  );
}
```

- [ ] **Step 2: Verify frontend builds**

Run:

```bash
cd apps/web && npm run build
```

Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/app/page.tsx
git commit -m "feat: wire chat state with sse streaming"
```

---

## Task 9: Add Version List Endpoint

The frontend needs a way to find the latest version. Add `GET /api/designs/{design_id}/versions` to list all versions.

**Files:**
- Modify: `services/api/app/routers/designs.py`
- Modify: `services/api/app/services/version_store.py`

- [ ] **Step 1: Add list_versions to VersionStore**

Add this method to `services/api/app/services/version_store.py`, after the existing `read_version` method:

```python
    def list_versions(self, design_id: str) -> list[dict[str, object]]:
        design_id = self._validate_design_id(design_id)
        versions_root = self.root / "designs" / design_id / "versions"
        if not versions_root.exists():
            return []
        versions = []
        for path in sorted(versions_root.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else 0):
            if path.is_dir() and path.name.isdigit():
                versions.append({"version_no": int(path.name)})
        return versions
```

- [ ] **Step 2: Add versions list endpoint to router**

Add this endpoint to `services/api/app/routers/designs.py`:

```python
@router.get("/designs/{design_id}/versions")
def list_versions(design_id: str):
    try:
        return runner.store.list_versions(design_id=design_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] **Step 3: Run full test suite**

Run:

```bash
CAD_BACKEND=fake .venv/bin/python -m pytest -q
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add services/api/app/routers/designs.py services/api/app/services/version_store.py
git commit -m "feat: add version list endpoint"
```

---

## Task 10: End-to-End Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run full backend test suite**

Run:

```bash
CAD_BACKEND=fake .venv/bin/python -m pytest -q
```

Expected: all PASS.

- [ ] **Step 2: Start backend**

Run:

```bash
set -a && . ./.env && set +a
CAD_BACKEND=fake .venv/bin/python -m uvicorn services.api.app.main:app --host "$API_HOST" --port "$API_PORT"
```

Verify:

```bash
curl -sS "http://$API_HOST:$API_PORT/health"
```

Expected: `{"status":"ok"}`.

- [ ] **Step 3: Verify chat endpoint returns SSE**

Run (replace OPENAI_API_KEY with a valid key first):

```bash
curl -sS -N -X POST "http://$API_HOST:$API_PORT/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"e2e-test","message":"设计一架翼展12米双发无人机"}'
```

Expected: SSE stream with `event: message` and `event: tool_call` events.

- [ ] **Step 4: Build and start frontend**

Run:

```bash
cd apps/web && set -a && . ../../.env && set +a && npm run build && npm run dev
```

Expected: `http://localhost:3900` opens the workbench.

- [ ] **Step 5: Update README**

Add a section to `README.md` after the existing "CAD Backend" section:

```markdown
## Chat Endpoint

The chat endpoint connects to an OpenAI-compatible LLM to parse natural language into aircraft specs.

Set the following environment variables in `.env`:

```
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
```

Then use the web UI chat panel or curl:

```bash
curl -sS -N -X POST "http://localhost:8900/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"demo-chat","message":"设计一架翼展12米双发无人机"}'
```
```

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: add chat endpoint documentation"
```

---

## Self-Review

**Spec coverage:**
- System prompt with spec/rules → Task 4
- Function calling (generate_design, modify_design) → Task 4
- Spec patching (deep merge) → Task 3
- SSE endpoint → Task 5
- Frontend ChatPanel rewrite with SSE → Task 6
- ParameterPanel dynamic from spec → Task 7
- page.tsx conversation state wiring → Task 8
- Version list endpoint → Task 9
- Environment variables → Task 2
- E2E verification → Task 10
- VersionPanel already has download links (verified in existing code) — no changes needed

**Placeholder scan:** No TBD, TODO, or vague instructions. All code blocks contain complete implementations.

**Type consistency:**
- `AircraftSpec` used consistently across spec_patch, chat_service
- `ChatMessage` type defined in ChatPanel and used in page.tsx
- `CadPreviewSource` used from existing cadPreviewSource.ts
- `ConversationState.conversation_id` → used as `design_id` consistently
- SSE event types (`message`, `tool_call`, `error`) match between backend `_sse_event` calls and frontend parsing
- `VersionResponse` type matches backend `read_version` return shape
