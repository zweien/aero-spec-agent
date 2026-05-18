# LangGraph Main Flow Migration Plan

## Goal

Migrate ChatService from direct OpenAI API calls + manual tool dispatch to a LangGraph StateGraph, enabling structured state management, conditional routing, and future multi-agent orchestration.

## Current Architecture

```
User message
  → ChatService.chat_stream()
    → OpenAI streaming call (with tools)
    → Manual tool dispatch (generate_design / modify_design / modify_selected_part)
    → OpenAI streaming call (final response)
  → SSE events to frontend
```

Pain points:
- Tool dispatch is a manual if/elif chain (chat_service.py lines 371-427)
- State management is ad-hoc JSON in memory + file
- Intent classification exists but is only used for shadow mode
- No graph visualization, no checkpointing, no branching

## Target Architecture

```
User message
  → LangGraph StateGraph (compiled with optional InMemorySaver)
    → load_context node (state hydration)
    → classify_intent node (route to correct tool path)
    → generate_design / modify_design / modify_selected_part node (shadow: would_call only)
    → save_state node
  → SSE events (via astream_events v2 or stream_events v3)
```

## State Schema (DesignGraphState)

Uses `TypedDict` with annotated reducers for accumulation fields:

```python
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated

class DesignGraphState(TypedDict, total=False):
    # Identity
    conversation_id: str
    design_id: str

    # Input
    user_message: str
    selected_refs: list[str]

    # Context — add_messages reducer (dedup, ID-based update, shorthand support)
    current_spec: dict[str, Any] | None
    messages: Annotated[list[AnyMessage], add_messages]

    # Intent classification
    intent: DesignIntent  # Literal["generate_design", "modify_design", ...]

    # Tool execution results
    tool_name: str
    tool_args: dict[str, Any]

    # Shadow-mode metadata (written but never executed)
    would_call_tool: str
    would_call_args: dict[str, Any]

    # Error accumulation — operator.add reducer
    graph_errors: Annotated[list[str], operator.add]
    ...
```

Key patterns:
- `messages: Annotated[list[AnyMessage], add_messages]` — LangGraph built-in reducer handles deduplication, ID-based message updates, and OpenAI-format shorthand
- `graph_errors: Annotated[list[str], operator.add]` — append-only error accumulation across nodes
- Fields without reducers use default overwrite semantics

## Graph Construction

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

def build_design_graph(checkpointer: InMemorySaver | None = None):
    graph = StateGraph(DesignGraphState)
    graph.add_node("load_context", load_context)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("generate_design", generate_design)
    graph.add_node("modify_design", modify_design)
    graph.add_node("modify_selected_part", modify_selected_part)
    graph.add_node("save_state", save_state)

    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "classify_intent")
    graph.add_conditional_edges("classify_intent", _route_by_intent, {...})
    graph.add_edge("generate_design", "save_state")
    graph.add_edge("modify_design", "save_state")
    graph.add_edge("modify_selected_part", "save_state")
    graph.add_edge("save_state", END)

    return graph.compile(checkpointer=checkpointer)
```

- Without checkpointer: `graph = build_design_graph()` — stateless, single invocation
- With checkpointer: `graph = build_design_graph(checkpointer=InMemorySaver())` — thread-based persistence
- Thread ID: `config = {"configurable": {"thread_id": "..."}}`

## Shadow Mode Nodes

In shadow mode, tool nodes never execute real jobs. They only record `would_call_tool` and `would_call_args` for divergence comparison:

```python
def generate_design(state: DesignGraphState) -> dict:
    return {
        "tool_name": "generate_design",
        "tool_args": {},
        "would_call_tool": "generate_design",
        "would_call_args": {"design_id": state.get("design_id", ""), ...},
    }
```

## Streaming

### astream_events (v2)

Async event streaming with `{event, name, data}` format:

```python
config = {"configurable": {"thread_id": "t1"}}
async for event in graph.astream_events(input_state, config=config, version="v2"):
    if event["event"] == "on_chain_start":
        print(f"Starting: {event['name']}")
```

Event types: `on_chain_start`, `on_chain_stream`, `on_chain_end`

### stream_events (v3, experimental)

Sync protocol-event streaming with typed projections:

```python
for event in graph.stream_events(input_state, config=config, version="v3"):
    # event = {method: "values", params: {namespace: [], data: ...}}
```

## Three-Phase Migration

### Phase 1: Shadow Mode (zero risk) — CURRENT

Run LangGraph in parallel with current ChatService. Compare outputs without affecting users.

**Implementation:**
- Build `DesignStateGraph` in `services/api/app/graph/` using `DesignGraphState` TypedDict
- Wire up nodes: `load_context`, `classify_intent`, `generate_design`, `modify_design`, `modify_selected_part`
- Each node wraps existing ChatService methods (no logic duplication)
- Add `/api/chat/shadow` endpoint that runs both old and new paths
- Tool nodes write `would_call_tool`/`would_call_args` — never execute real jobs
- Log divergence via `ShadowLogger`
- Checkpointing via `InMemorySaver` with `thread_id`

**Exit criteria:** Divergence rate < 5% over 100+ conversations.

### Phase 2: Partial Mode (low risk)

Replace specific tool handlers with LangGraph nodes while keeping the main ChatService flow.

**Implementation:**
- `classify_intent` node replaces `classify_message_intent()` shadow call → becomes the real router
- `generate_design` node replaces `_handle_generate_design()` direct call
- `modify_design` node replaces `_handle_modify_design()` direct call
- `modify_selected_part` node replaces `_handle_modify_selected_part()` direct call
- SSE streaming via `astream_events(version="v2")` with custom event emitter
- Fallback: if LangGraph raises, fall back to old ChatService path

**Exit criteria:** Zero regressions in tool call accuracy, SSE streaming latency < 200ms overhead.

### Phase 3: Main Mode (full migration)

ChatService becomes a thin wrapper around LangGraph.

**Implementation:**
- `ChatService.chat_stream()` delegates to `DesignStateGraph.astream()`
- State management moves to LangGraph checkpointing (SQLite or PostgreSQL)
- Tool definitions become LangGraph tool nodes
- System prompt construction becomes a graph node
- Remove old manual dispatch code
- Add graph visualization endpoint (`/api/chat/graph/{conversation_id}`)

**Exit criteria:** All existing tests pass unchanged. New graph-specific tests added.

## Testing Strategy

1. **Unit tests per node**: Each node tested in isolation with mock dependencies
2. **Integration tests**: Full graph execution with fake backend
3. **Shadow comparison tests**: Old path vs new path on recorded conversations
4. **SSE contract tests**: Verify event format unchanged
5. **Streaming tests**: `astream_events(version="v2")` event sequence validation
6. **Thread isolation tests**: Separate `thread_id` values produce independent state
7. **Message accumulation tests**: `add_messages` reducer preserves existing messages

Test file: `tests/api/test_langgraph_shadow_runtime.py` (8 test scenarios)

## Dependencies

- `langgraph>=1.2.0` — StateGraph, InMemorySaver, add_messages reducer
- `langchain-openai>=1.2.0` — ChatOpenAI integration
- `langchain-core>=1.4.0` — AnyMessage, BaseMessage abstractions

## Risks

| Risk | Mitigation |
|------|-----------|
| SSE streaming format breaks | Shadow mode comparison + contract tests |
| State serialization incompatibility | Checkpoint migration script |
| Latency regression | Benchmark old vs new in shadow mode |
| LangGraph dependency versioning | Pin versions, test upgrade path separately |
| v3 streaming protocol changes | Use v2 for production, v3 for experimentation |
