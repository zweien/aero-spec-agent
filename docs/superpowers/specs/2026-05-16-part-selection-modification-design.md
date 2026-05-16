# Part Selection Modification Design

Date: 2026-05-16

## Goal

Allow users to click any aircraft part in the 3D viewer, then use natural language in chat to modify that part's parameters via the LLM-calling `modify_selected_part` tool.

## Current State

- 3D picking works for fuselage, main_wing, tail, left_engine, right_engine
- `selected_refs` (e.g. `["part:right_engine"]`) flows from click → state → chat API → LLM system prompt
- `modify_selected_part` tool exists but only supports engine movement (6 direction offsets)
- Fuselage, wing, and tail parts are selectable but have no modification operations

## Design

### Tool Schema Changes

Extend the `modify_selected_part` tool in `chat_service.py`:

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `part_ref` | string enum | yes | `part:fuselage`, `part:main_wing`, `part:tail`, `part:left_engine`, `part:right_engine` |
| `operation` | string enum | yes | See operation table below |
| `value` | number | yes | Absolute target value for `set_*`, incremental delta for `move_*` |
| `reason` | string | no | Modification reason |

**Operation Enum:**

| Operation | Allowed part_ref | Spec Path | Semantics |
|-----------|-----------------|-----------|-----------|
| `set_length` | `part:fuselage` | `fuselage.length` | absolute (m) |
| `set_diameter` | `part:fuselage` | `fuselage.max_diameter` | absolute (m) |
| `set_span` | `part:main_wing` | `wing.span` | absolute (m) |
| `set_root_chord` | `part:main_wing` | `wing.root_chord` | absolute (m) |
| `set_tip_chord` | `part:main_wing` | `wing.tip_chord` | absolute (m) |
| `set_sweep` | `part:main_wing` | `wing.sweep` | absolute (deg) |
| `set_dihedral` | `part:main_wing` | `wing.dihedral` | absolute (deg) |
| `set_tail_type` | `part:tail` | `tail.type` | absolute (string — but `value` remains number for schema simplicity; backend converts) |
| `move_outboard` | `part:left_engine`, `part:right_engine` | `engine.y_offset` | incremental (m) |
| `move_inboard` | `part:left_engine`, `part:right_engine` | `engine.y_offset` | incremental (m) |
| `move_forward` | `part:left_engine`, `part:right_engine` | `engine.x_offset` | incremental (m) |
| `move_backward` | `part:left_engine`, `part:right_engine` | `engine.x_offset` | incremental (m) |
| `move_up` | `part:left_engine`, `part:right_engine` | `engine.z_offset` | incremental (m) |
| `move_down` | `part:left_engine`, `part:right_engine` | `engine.z_offset` | incremental (m) |

**Note on `set_tail_type`**: `tail.type` is a `TextScalar` (string value), but the tool schema uses `value: number` for all operations. For `set_tail_type`, the backend accepts the value as a string fallback. If this proves awkward, add a separate `text_value: string` optional parameter. The recommended approach is to change `value` type to `number | string` in the schema.

### Backend Changes

**File: `services/api/app/services/chat_service.py`**

1. **Update `MODIFY_SELECTED_PART_TOOL` schema:**
   - Rename `delta_m` → `value` (type: `number`)
   - Expand `operation` enum to include all operations above
   - Update description to list supported operations per part type

2. **Add operation routing map:**
   ```python
   _PART_OPERATIONS: dict[str, dict[str, tuple[str, str]]] = {
       "part:fuselage": {
           "set_length":   ("fuselage", "length"),
           "set_diameter": ("fuselage", "max_diameter"),
       },
       "part:main_wing": {
           "set_span":       ("wing", "span"),
           "set_root_chord": ("wing", "root_chord"),
           "set_tip_chord":  ("wing", "tip_chord"),
           "set_sweep":      ("wing", "sweep"),
           "set_dihedral":   ("wing", "dihedral"),
       },
       "part:tail": {
           "set_tail_type": ("tail", "type"),
       },
   }
   ```

3. **Rewrite `_handle_modify_selected_part`:**
   - Engine `move_*` operations: keep existing incremental logic unchanged
   - New `set_*` operations:
     1. Validate `part_ref ↔ operation` combination via `_PART_OPERATIONS`
     2. Pre-fill `None` scalar fields (e.g. `wing.sweep`, `wing.dihedral`) with default structure
     3. Set `value` on the target field, `source="user"`, `confidence=1.0`
     4. Validate patched spec with `AircraftSpec.model_validate()`
     5. Trigger generation via `JobRunner`
     6. Stream SSE events (tool_start → generation progress → generation_complete)
   - For `set_tail_type`: handle TextScalar by setting `value` as string

4. **Update system prompt template:**
   - Remove "第一版主要支持发动机位置调整" limitation text
   - Add brief description of supported operations per part type

### Frontend Changes

**File: `apps/web/src/components/chat/ChatPanel.tsx`**

1. Update `OPERATION_LABELS` map with new operations:
   ```typescript
   "set_length": "设置长度",
   "set_diameter": "设置直径",
   "set_span": "设置翼展",
   // ... etc
   ```

2. Update `SpecSummary` to render `value` field (currently only renders `delta_m`)

3. No changes to 3D picking, selected_refs flow, or parameter panel

### Validation

- Invalid `part_ref ↔ operation` combinations return error via SSE
- `set_tail_type` validates against allowed tail type values
- All `set_*` values are validated through `AircraftSpec.model_validate()` before generation

### Testing

- Add tests for each new operation to `tests/api/test_chat_service.py`
- Test invalid combinations (e.g., `set_length` on `part:main_wing`)
- Test `set_sweep` and `set_dihedral` with `None` → pre-fill → set flow
