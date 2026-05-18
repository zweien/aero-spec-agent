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
  → LangGraph StateGraph
    → load_context node (state hydration)
    → classify_intent node (route to correct tool path)
    → generate_design / modify_design / modify_selected_part node
    → synthesize_response node (final LLM call)
    → save_state node
  → SSE events (via custom callback or stream adapter)
```

## Three-Phase Migration

### Phase 1: Shadow Mode (zero risk)

Run LangGraph in parallel with current ChatService. Compare outputs without affecting users.

**Implementation:**
- Build `DesignStateGraph` in `services/api/app/graph/` using existing `DesignGraphState` TypedDict
- Wire up nodes: `load_context`, `classify_intent`, `generate_design`, `modify_design`, `modify_selected_part`, `synthesize_response`
- Each node wraps existing ChatService methods (no logic duplication)
- Add `/api/chat/shadow` endpoint that runs both old and new paths
- Log divergence (intent mismatch, different tool calls, different response quality)
- Run for 2+ weeks, measure divergence rate

**Exit criteria:** Divergence rate < 5% over 100+ conversations.

### Phase 2: Partial Mode (low risk)

Replace specific tool handlers with LangGraph nodes while keeping the main ChatService flow.

**Implementation:**
- `classify_intent` node replaces `classify_message_intent()` shadow call → becomes the real router
- `generate_design` node replaces `_handle_generate_design()` direct call
- `modify_design` node replaces `_handle_modify_design()` direct call
- `modify_selected_part` node replaces `_handle_modify_selected_part()` direct call
- SSE streaming via LangGraph `astream_events()` with custom event emitter
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

## Node Specifications

### load_context
- Input: conversation_id, user_message
- Loads: ConversationState from storage (messages, current_spec, selected_refs, design_id)
- Output: DesignGraphState with hydrated context

### classify_intent
- Input: DesignGraphState
- Uses: LLM to classify intent (generate / modify / modify_selected_part / conversation)
- Output: DesignGraphState with intent field set
- Routing: conditional edge to correct tool node or direct to synthesize

### generate_design
- Input: DesignGraphState (with extracted spec from user message)
- Uses: JobRunner.enqueue_generate + BackgroundTasks
- Output: DesignGraphState with job_id, status
- SSE events: generation_started, generation_complete

### modify_design
- Input: DesignGraphState (with field changes from user message)
- Uses: spec_patch.apply_patch + JobRunner
- Output: DesignGraphState with patched spec and job_id
- SSE events: generation_started, generation_complete

### modify_selected_part
- Input: DesignGraphState (with selected_refs + operation from user message)
- Uses: selected_part_modifier.apply_selected_part_patch + JobRunner
- Output: DesignGraphState with patched spec and job_id
- SSE events: generation_started, generation_complete

### synthesize_response
- Input: DesignGraphState (with tool results)
- Uses: LLM streaming call
- Output: DesignGraphState with final response
- SSE events: message chunks

### save_state
- Input: DesignGraphState
- Persists: ConversationState to storage
- Output: DesignGraphState (unchanged)

## Dependencies

- `langgraph>=0.2.0` — StateGraph, checkpointing
- `langchain-openai>=0.2.0` — ChatOpenAI integration
- `langchain-core>=0.3.0` — Base abstractions

## SSE Streaming Adapter

LangGraph's `astream_events()` emits typed events. We need an adapter:

```python
async def langgraph_event_to_sse(event: dict) -> str | None:
    """Convert LangGraph stream event to SSE format."""
    kind = event.get("event")
    if kind == "on_chat_model_stream":
        chunk = event["data"]["chunk"].content
        return _sse_event("message", {"content": chunk})
    if kind == "on_tool_start":
        return _sse_event("tool_call", {
            "name": event["name"],
            "arguments": json.dumps(event["data"]["input"]),
        })
    # ... map other events
    return None
```

## Testing Strategy

1. **Unit tests per node**: Each node tested in isolation with mock dependencies
2. **Integration tests**: Full graph execution with fake backend
3. **Shadow comparison tests**: Old path vs new path on recorded conversations
4. **SSE contract tests**: Verify event format unchanged

## Risks

| Risk | Mitigation |
|------|-----------|
| SSE streaming format breaks | Shadow mode comparison + contract tests |
| State serialization incompatibility | Checkpoint migration script |
| Latency regression | Benchmark old vs new in shadow mode |
| LangGraph dependency versioning | Pin versions, test upgrade path separately |
