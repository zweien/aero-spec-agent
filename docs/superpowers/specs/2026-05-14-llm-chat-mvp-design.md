# LLM Chat MVP Design

> Status: approved
> Date: 2026-05-14

## Goal

Add natural-language chat to AeroSpec Agent so users can describe aircraft requirements in plain text, get a parametric spec generated via LLM, trigger CAD generation, and iteratively modify the design through multi-turn conversation — with SSE streaming throughout.

## Context

The current codebase has a working pipeline: hand-written YAML → FastAPI → fake/openvsp CAD backend → versioned file storage. The web UI has a three-panel layout with a "Generate" button that sends a hardcoded example spec. The missing piece is the LLM-powered conversational entry point.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| LLM provider | OpenAI-compatible domestic model | User requirement; use `openai` SDK with `OPENAI_BASE_URL` |
| Agent framework | None (lightweight loop) | MVP doesn't need LangGraph; simple state dict + function calling |
| Streaming | SSE via FastAPI `StreamingResponse` | Real-time UX without WebSockets complexity |
| Spec patching | Deep merge on backend | LLM outputs only changed fields; backend validates the full result |
| Conversation state | In-memory dict keyed by conversation_id | Single-user local deployment; no DB needed |
| Deployment | Local single-machine | No auth, HTTPS, or concurrency concerns |

## Backend Design

### New endpoint: `POST /api/chat`

Request body:
```json
{
  "conversation_id": "uuid-string",
  "message": "设计一架翼展12米双发无人机"
}
```

Response: SSE stream (`text/event-stream`).

SSE event types:
- `message` — token-by-token assistant text (field: `content`)
- `tool_call` — function name and arguments being executed
- `generation_started` — CAD generation job submitted
- `generation_complete` — job result with version info
- `error` — error message

### ChatService

Manages per-conversation state:

```python
class ConversationState:
    conversation_id: str
    design_id: str
    messages: list[dict]          # chat history for LLM context
    current_spec: AircraftSpec | None
```

Process:
1. Load or create `ConversationState` for the given `conversation_id`
2. Append user message to history
3. Build system prompt with current spec (YAML) + AircraftSpec schema
4. Call LLM with function definitions (`generate_design`, `modify_design`)
5. Stream text tokens as `message` SSE events
6. If LLM invokes a function:
   - Stream `tool_call` event
   - Execute the function (validate spec → JobRunner.generate)
   - Stream `generation_started` / `generation_complete` events
   - Feed tool result back to LLM for final explanation
7. Append assistant response to history
8. Update `current_spec` if generation succeeded

### Function Calling

`generate_design` — create a new spec from scratch:
```json
{
  "name": "generate_design",
  "description": "Generate a new aircraft design from user requirements",
  "parameters": {
    "type": "object",
    "properties": {
      "spec": { "$ref": "#/definitions/AircraftSpec" }
    },
    "required": ["spec"]
  }
}
```

`modify_design` — patch the existing spec:
```json
{
  "name": "modify_design",
  "description": "Modify the current aircraft design parameters",
  "parameters": {
    "type": "object",
    "properties": {
      "changes": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "path": { "type": "string", "description": "dot-separated field path, e.g. wing.span.value" },
            "value": { "description": "new value" },
            "reason": { "type": "string" }
          },
          "required": ["path", "value"]
        }
      }
    },
    "required": ["changes"]
  }
}
```

### Spec patching

`spec_patch.py` implements deep merge:

```python
def apply_patch(spec: AircraftSpec, changes: list[Change]) -> AircraftSpec:
    """Deep-merge changes into spec, return re-validated AircraftSpec."""
    data = spec.model_dump(mode="json")
    for change in changes:
        _set_nested(data, change.path, change.value)
    return AircraftSpec.model_validate(data)
```

Validation errors are returned to the LLM as tool results so it can self-correct.

### System Prompt

```
你是 AeroSpec Agent，一个飞机概念设计助手。

用户用自然语言描述飞机需求，你负责生成或修改 aircraft_spec 参数化设计。

当前设计状态：
{current_spec_yaml 或 "尚无设计"}

规则：
- 只处理固定翼无人机（fixed_wing_uav），常规布局（conventional）
- 所有数值参数必须包含 unit、source、confidence 字段
- 用户明确给出的参数：source=user, confidence=1.0
- 你推断的参数：source=inferred, confidence=0.7-0.9
- 无法确定的参数使用合理默认值：source=rule_default, confidence=0.7
- 新建设计使用 generate_design，修改现有设计使用 modify_design
- 修改时只输出需要变更的字段
- 生成完成后简要解释设计参数和依据
```

### Environment variables

```
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com/v1   # or other compatible endpoint
OPENAI_MODEL=deepseek-chat                      # or other model name
```

## Frontend Design

### ChatPanel rewrite

- Maintain `conversationId` (UUID generated on first message)
- Maintain `messages: Array<{role: 'user' | 'assistant', content: string}>`
- On send: POST to `/api/chat`, read response as SSE via `fetch` + `ReadableStream`
- Parse SSE events:
  - `message`: append token to current assistant message
  - `generation_started`: show spinner on CadViewer
  - `generation_complete`: refresh model + params + version
  - `error`: show error toast
- Auto-scroll to bottom on new content

### ParameterPanel — dynamic from spec

- After each generation, read full spec from `validation_report.spec_echo`
- Build parameter rows from spec data instead of hardcoded list
- Show source badge (user/inferred/rule_default) and confidence percentage

### VersionPanel — download links

- File names become clickable `<a>` tags pointing to `/api/designs/{id}/versions/{no}/files/{name}`

### page.tsx

- Wire conversationId and messages state
- Pass generation callbacks from chat flow to CadViewer/ParameterPanel/VersionPanel

## Files to Create

- `services/api/app/routers/chat.py`
- `services/api/app/services/chat_service.py`
- `services/api/app/services/spec_patch.py`
- `tests/api/test_spec_patch.py`
- `tests/api/test_chat_service.py`
- `tests/api/test_chat_api.py`

## Files to Modify

- `services/api/app/main.py` — register chat router, update CORS
- `apps/web/src/app/page.tsx` — conversation state management
- `apps/web/src/components/chat/ChatPanel.tsx` — SSE streaming rewrite
- `apps/web/src/components/parameter-panel/ParameterPanel.tsx` — dynamic params
- `apps/web/src/components/version-panel/VersionPanel.tsx` — download links
- `pyproject.toml` — add `openai>=1.30.0` dependency
- `.env` — add OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

## Files to Commit (existing uncommitted)

- `services/workers/cad_worker/openvsp_generator/obj_to_glb.py`
- `tests/api/test_obj_to_glb.py`
- `apps/web/src/components/cad-viewer/cadPreviewStatus.ts`
- `apps/web/src/components/cad-viewer/cadPreviewStatus.test.ts`
- `pyproject.toml` (trimesh dependency)
- CSS and component adjustments

## Out of Scope

- LangGraph orchestration
- Database persistence (PostgreSQL)
- Redis task queue
- User authentication
- CAD object selection / @cad[...] references
- VSPAERO / aerodynamic analysis
- Parameter panel manual editing
- Multi-user concurrency
