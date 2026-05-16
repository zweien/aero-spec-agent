from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.spec_io import dump_aircraft_spec
from services.api.app.services.spec_patch import _set_nested

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flat field definitions: field_name → (scalar_type, default_unit, spec_path)
# ---------------------------------------------------------------------------
FLAT_FIELD_DEFS: dict[str, tuple[str, str | None, str]] = {
    "name":              ("text",    None,    "aircraft.name"),
    "wing_span":         ("numeric", "m",     "wing.span"),
    "wing_root_chord":   ("numeric", "m",     "wing.root_chord"),
    "wing_tip_chord":    ("numeric", "m",     "wing.tip_chord"),
    "wing_sweep":        ("numeric", "deg",   "wing.sweep"),
    "wing_dihedral":     ("numeric", "deg",   "wing.dihedral"),
    "wing_airfoil":      ("text",    None,    "wing.airfoil"),
    "wing_position":     ("text",    None,    "wing.position"),
    "fuselage_length":   ("numeric", "m",     "fuselage.length"),
    "fuselage_diameter": ("numeric", "m",     "fuselage.max_diameter"),
    "engine_count":      ("integer", None,    "engine.count"),
    "engine_position":   ("text",    None,    "engine.position"),
    "engine_x_offset":   ("numeric", "m",     "engine.x_offset"),
    "engine_y_offset":   ("numeric", "m",     "engine.y_offset"),
    "engine_z_offset":   ("numeric", "m",     "engine.z_offset"),
    "tail_type":         ("text",    None,    "tail.type"),
    "cruise_speed":      ("numeric", "km/h",  "mission.cruise_speed"),
    "payload":           ("numeric", "kg",    "mission.payload"),
    "priority":          ("text",    None,    "mission.priority"),
}

# modify_design: field_name → spec dot-path (到 .value)
FIELD_TO_SPEC_PATH: dict[str, str] = {
    "name": "aircraft.name",
    "wing_span": "wing.span.value",
    "wing_root_chord": "wing.root_chord.value",
    "wing_tip_chord": "wing.tip_chord.value",
    "wing_sweep": "wing.sweep.value",
    "wing_dihedral": "wing.dihedral.value",
    "wing_airfoil": "wing.airfoil.value",
    "wing_position": "wing.position.value",
    "fuselage_length": "fuselage.length.value",
    "fuselage_diameter": "fuselage.max_diameter.value",
    "engine_count": "engine.count.value",
    "engine_position": "engine.position.value",
    "engine_x_offset": "engine.x_offset.value",
    "engine_y_offset": "engine.y_offset.value",
    "engine_z_offset": "engine.z_offset.value",
    "tail_type": "tail.type.value",
    "cruise_speed": "mission.cruise_speed.value",
    "payload": "mission.payload.value",
    "priority": "mission.priority.value",
}

# modify_design: 数值字段修改时需同时填充 unit
FIELD_DEFAULT_UNIT: dict[str, str | None] = {
    "wing_span": "m", "wing_root_chord": "m", "wing_tip_chord": "m",
    "wing_sweep": "deg", "wing_dihedral": "deg",
    "fuselage_length": "m", "fuselage_diameter": "m",
    "engine_count": None, "engine_position": None,
    "engine_x_offset": "m", "engine_y_offset": "m", "engine_z_offset": "m",
    "cruise_speed": "km/h", "payload": "kg",
}

# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def _flat_args_to_spec(args: dict[str, Any]) -> AircraftSpec:
    """Convert flat generate_design args to full AircraftSpec with metadata."""
    inferred_fields = set(args.get("inferred_fields", []))

    spec_data: dict[str, Any] = {
        "schema_version": "0.1",
        "aircraft": {
            "name": args.get("name", "unnamed_uav"),
            "type": "fixed_wing_uav",
            "layout": "conventional",
        },
        "mission": {},
        "fuselage": {},
        "wing": {},
        "tail": {},
        "engine": {},
    }

    for field_name, (scalar_type, default_unit, spec_path) in FLAT_FIELD_DEFS.items():
        if field_name not in args:
            continue
        value = args[field_name]
        keys = spec_path.split(".")
        target = spec_data
        for key in keys[:-1]:
            target = target.setdefault(key, {})
        last_key = keys[-1]

        # aircraft.* fields are plain strings, not scalars
        if keys[0] == "aircraft":
            target[last_key] = str(value)
        else:
            source = "inferred" if field_name in inferred_fields else "user"
            confidence = 0.75 if source == "inferred" else 1.0
            if scalar_type == "text":
                target[last_key] = {"value": str(value), "source": source, "confidence": confidence}
            elif scalar_type == "integer":
                target[last_key] = {"value": int(value), "source": source, "confidence": confidence}
            else:
                scalar: dict[str, Any] = {"value": float(value), "source": source, "confidence": confidence}
                if default_unit:
                    scalar["unit"] = default_unit
                target[last_key] = scalar

    return AircraftSpec.model_validate(spec_data)


def _pre_fill_none_scalars(data: dict[str, Any], paths: list[str]) -> None:
    """Replace None scalar fields (only those being patched) with empty dicts.

    Paths like "wing.sweep.value" → check if "wing.sweep" is None, replace with {}.
    """
    for path in paths:
        keys = path.split(".")
        if len(keys) < 2:
            continue
        # Navigate to the parent of the last key (e.g. wing.sweep from wing.sweep.value)
        parent_keys = keys[:-1]
        scalar_key = parent_keys[-1]  # e.g. "sweep"
        current = data
        for key in parent_keys[:-1]:
            if not isinstance(current, dict) or key not in current:
                break
            current = current[key]
        else:
            if isinstance(current, dict) and current.get(scalar_key) is None:
                current[scalar_key] = {}


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

GENERATE_DESIGN_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "generate_design",
        "description": "根据用户需求生成新的飞机设计。当用户描述全新的飞机需求时使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "飞机名称，英文下划线命名"},
                "fuselage_length": {"type": "number", "description": "机身长度 (m)"},
                "fuselage_diameter": {"type": "number", "description": "机身最大直径 (m)"},
                "wing_position": {
                    "type": "string",
                    "enum": ["high", "low", "mid"],
                    "description": "机翼位置",
                },
                "wing_span": {"type": "number", "description": "翼展 (m)"},
                "wing_root_chord": {"type": "number", "description": "翼根弦长 (m)"},
                "wing_tip_chord": {"type": "number", "description": "翼尖弦长 (m)"},
                "wing_sweep": {"type": "number", "description": "机翼后掠角 (deg)"},
                "wing_dihedral": {"type": "number", "description": "机翼上反角 (deg)"},
                "wing_airfoil": {"type": "string", "description": "翼型，如 NACA4412"},
                "tail_type": {
                    "type": "string",
                    "enum": ["conventional", "t-tail", "v-tail"],
                    "description": "尾翼类型",
                },
                "engine_count": {"type": "integer", "description": "发动机数量"},
                "engine_position": {
                    "type": "string",
                    "enum": ["under_wing", "on_fuselage", "wing_tip", "rear_fuselage"],
                    "description": "发动机位置",
                },
                "cruise_speed": {"type": "number", "description": "巡航速度 (km/h)"},
                "payload": {"type": "number", "description": "有效载荷 (kg)"},
                "priority": {
                    "type": "string",
                    "enum": ["endurance", "speed", "payload", "range"],
                    "description": "设计优先级",
                },
                "inferred_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "哪些参数是你根据经验推断，而不是用户明确给出",
                },
            },
            "required": [
                "name", "fuselage_length", "wing_position",
                "wing_span", "wing_root_chord", "wing_tip_chord",
                "tail_type", "engine_count",
            ],
        },
    },
}

MODIFY_DESIGN_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "modify_design",
        "description": "修改当前飞机设计的参数。使用语义化字段名指定要修改的参数。",
        "parameters": {
            "type": "object",
            "properties": {
                "changes": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {
                                "type": "string",
                                "enum": list(FIELD_TO_SPEC_PATH.keys()),
                                "description": "要修改的参数名",
                            },
                            "value": {"description": "新值"},
                            "reason": {"type": "string", "description": "修改原因"},
                        },
                        "required": ["field", "value"],
                    },
                }
            },
            "required": ["changes"],
        },
    },
}

MODIFY_SELECTED_PART_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "modify_selected_part",
        "description": (
            "修改选中的飞机部件参数。根据当前 selected_refs 确定部件类型。\n"
            "支持的操作：\n"
            "- 机身(part:fuselage): set_length(设置长度/m), set_diameter(设置直径/m)\n"
            "- 机翼(part:main_wing): set_span(设置翼展/m), set_root_chord(设置翼根弦长/m), "
            "set_tip_chord(设置翼尖弦长/m), set_sweep(设置后掠角/deg), set_dihedral(设置上反角/deg)\n"
            "- 尾翼(part:tail): set_tail_type(设置尾翼类型)\n"
            "- 发动机(part:left_engine/part:right_engine): move_outboard/inboard/forward/backward/up/down(移动/m，增量)\n"
            "set_* 操作 value 为目标绝对值；move_* 操作 value 为移动距离增量。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "part_ref": {
                    "type": "string",
                    "enum": [
                        "part:left_engine",
                        "part:right_engine",
                        "part:fuselage",
                        "part:main_wing",
                        "part:tail",
                    ],
                    "description": "要修改的部件引用，通常来自当前 selected_refs",
                },
                "operation": {
                    "type": "string",
                    "enum": [
                        "set_length",
                        "set_diameter",
                        "set_span",
                        "set_root_chord",
                        "set_tip_chord",
                        "set_sweep",
                        "set_dihedral",
                        "set_tail_type",
                        "move_outboard",
                        "move_inboard",
                        "move_forward",
                        "move_backward",
                        "move_up",
                        "move_down",
                    ],
                    "description": "操作类型。set_* 用绝对值，move_* 用增量。",
                },
                "value": {
                    "description": "set_* 操作为目标绝对值，move_* 操作为移动增量 (m)",
                },
                "reason": {
                    "type": "string",
                    "description": "修改原因",
                },
            },
            "required": ["part_ref", "operation", "value"],
        },
    },
}

SYSTEM_PROMPT_TEMPLATE = """你是 AeroSpec Agent，一个飞机概念设计助手。

用户用自然语言描述飞机需求，你负责生成或修改参数化设计。

当前设计状态：
%s

当前选中对象：
{selected_refs}

规则：
- 只处理固定翼无人机（fixed_wing_uav），常规布局（conventional）
- 新建设计使用 generate_design，修改现有设计使用 modify_design
- 用户引用当前选中部件（如"这个发动机""选中的机翼""这个机身"）并要求修改参数时，使用 modify_selected_part
- modify_selected_part 支持所有部件：机身(长度/直径)、机翼(翼展/弦长/后掠角/上反角)、尾翼(类型)、发动机(位置移动)
- 用户明确给出的参数直接填入，其余参数根据航空工程经验推断合理默认值
- 如果某些参数是你根据经验补全的，请把字段名放入 inferred_fields
- 生成完成后简要解释设计参数和依据
"""


@dataclass
class ConversationState:
    conversation_id: str
    design_id: str
    messages: list[dict[str, str]] = field(default_factory=list)
    current_spec: AircraftSpec | None = None
    selected_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "design_id": self.design_id,
            "messages": self.messages,
            "current_spec": self.current_spec.model_dump(mode="json") if self.current_spec else None,
            "selected_refs": self.selected_refs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversationState:
        spec_data = data.get("current_spec")
        return cls(
            conversation_id=data["conversation_id"],
            design_id=data["design_id"],
            messages=data.get("messages", []),
            current_spec=AircraftSpec.model_validate(spec_data) if spec_data else None,
            selected_refs=list(data.get("selected_refs", [])),
        )


def _sse_event(event_type: str, data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else json.dumps({"content": data}, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"


class ChatService:
    def __init__(self, storage_root: str | Path | None = None) -> None:
        self._conversations: dict[str, ConversationState] = {}
        self._model = os.getenv("OPENAI_MODEL", "deepseek-chat")
        self._client: AsyncOpenAI | None = None
        self._job_runner = None
        self._storage_root = Path(storage_root) if storage_root else Path("storage")

    def _state_path(self, conversation_id: str) -> Path:
        return self._storage_root / "conversations" / conversation_id / "state.json"

    def _save_state(self, state: ConversationState) -> None:
        path = self._state_path(state.conversation_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            api_key = os.getenv("OPENAI_API_KEY", "")
            base_url = os.getenv("OPENAI_BASE_URL")
            saved_proxy = {}
            for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
                if val := os.environ.pop(key, None):
                    saved_proxy[key] = val
            try:
                self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            finally:
                os.environ.update(saved_proxy)
        return self._client

    def set_job_runner(self, runner: Any) -> None:
        self._job_runner = runner

    def get_or_create_state(self, conversation_id: str) -> ConversationState:
        if conversation_id not in self._conversations:
            state_path = self._state_path(conversation_id)
            if state_path.exists():
                try:
                    data = json.loads(state_path.read_text(encoding="utf-8"))
                    self._conversations[conversation_id] = ConversationState.from_dict(data)
                except Exception:
                    logger.warning("Failed to load conversation %s, creating fresh", conversation_id)
                    self._conversations[conversation_id] = ConversationState(
                        conversation_id=conversation_id,
                        design_id=conversation_id,
                    )
            else:
                self._conversations[conversation_id] = ConversationState(
                    conversation_id=conversation_id,
                    design_id=conversation_id,
                )
        return self._conversations[conversation_id]

    def build_tools(self) -> list[dict[str, Any]]:
        return [GENERATE_DESIGN_TOOL, MODIFY_DESIGN_TOOL, MODIFY_SELECTED_PART_TOOL]

    def _build_system_prompt(self, state: ConversationState) -> str:
        if state.current_spec is not None:
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                dump_aircraft_spec(state.current_spec, Path(f.name))
                spec_yaml = Path(f.name).read_text(encoding="utf-8")
            Path(f.name).unlink(missing_ok=True)
        else:
            spec_yaml = "尚无设计"
        selected_context = "\n".join(state.selected_refs) if state.selected_refs else "无"
        return (SYSTEM_PROMPT_TEMPLATE % spec_yaml).replace(
            "{selected_refs}",
            selected_context,
        )

    async def chat_stream(
        self,
        conversation_id: str,
        message: str,
        selected_refs: list[str] | None = None,
    ) -> AsyncIterator[str]:
        state = self.get_or_create_state(conversation_id)
        if selected_refs is not None:
            state.selected_refs = list(selected_refs)
        state.messages.append({"role": "user", "content": message})

        system_prompt = self._build_system_prompt(state)
        api_messages = [{"role": "system", "content": system_prompt}] + state.messages

        collected_content = ""
        tool_calls_collected: dict[int, dict[str, Any]] = {}

        try:
            response = await self._get_client().chat.completions.create(
                model=self._model,
                messages=api_messages,
                tools=self.build_tools(),
                stream=True,
            )

            async for chunk in response:
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
        except Exception as exc:
            error_msg = str(exc)
            yield _sse_event("error", {"content": error_msg})
            self._save_state(state)
            return

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
            self._save_state(state)
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
                state.messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": tool_result})
                continue

            if tool_name == "generate_design":
                async for event in self._handle_generate_design(state, tool_args, tool_call_id):
                    yield event
            elif tool_name == "modify_design":
                async for event in self._handle_modify_design(state, tool_args, tool_call_id):
                    yield event
            elif tool_name == "modify_selected_part":
                async for event in self._handle_modify_selected_part(state, tool_args, tool_call_id):
                    yield event
            else:
                state.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps({"error": f"unknown tool: {tool_name}"}, ensure_ascii=False),
                })

        final_content = ""
        try:
            second_response = await self._get_client().chat.completions.create(
                model=self._model,
                messages=[{"role": "system", "content": system_prompt}] + state.messages,
                stream=True,
            )

            async for chunk in second_response:
                choice = chunk.choices[0] if chunk.choices else None
                if choice and choice.delta and choice.delta.content:
                    final_content += choice.delta.content
                    yield _sse_event("message", choice.delta.content)
        except Exception as exc:
            yield _sse_event("error", {"content": str(exc)})
            self._save_state(state)
            return

        if final_content:
            state.messages.append({"role": "assistant", "content": final_content})

        self._save_state(state)

    async def _handle_generate_design(
        self, state: ConversationState, args: dict[str, Any], tool_call_id: str,
    ) -> AsyncIterator[str]:
        try:
            spec = _flat_args_to_spec(args)
        except Exception as exc:
            error_msg = f"spec 校验失败: {exc}"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({
                "role": "tool", "tool_call_id": tool_call_id,
                "content": json.dumps({"error": error_msg}, ensure_ascii=False),
            })
            return

        if self._job_runner is None:
            error_msg = "job runner not configured"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({
                "role": "tool", "tool_call_id": tool_call_id,
                "content": json.dumps({"error": error_msg}, ensure_ascii=False),
            })
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
            "role": "tool", "tool_call_id": tool_call_id,
            "content": json.dumps(result, ensure_ascii=False),
        })

    async def _handle_modify_design(
        self, state: ConversationState, args: dict[str, Any], tool_call_id: str,
    ) -> AsyncIterator[str]:
        if state.current_spec is None:
            error_msg = "没有当前设计，请先使用 generate_design 创建设计"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({
                "role": "tool", "tool_call_id": tool_call_id,
                "content": json.dumps({"error": error_msg}, ensure_ascii=False),
            })
            return

        changes = args.get("changes", [])
        if not changes:
            error_msg = "changes 不能为空，请提供至少一个变更项"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({
                "role": "tool", "tool_call_id": tool_call_id,
                "content": json.dumps({"error": error_msg}, ensure_ascii=False),
            })
            return

        # 转换语义化字段为点路径补丁
        patch_changes: list[dict[str, Any]] = []
        extra_patches: list[dict[str, Any]] = []
        for change in changes:
            field_name = change.get("field", "")
            if field_name not in FIELD_TO_SPEC_PATH:
                error_msg = f"未知字段: {field_name}，可选: {', '.join(FIELD_TO_SPEC_PATH.keys())}"
                yield _sse_event("error", {"content": error_msg})
                state.messages.append({
                    "role": "tool", "tool_call_id": tool_call_id,
                    "content": json.dumps({"error": error_msg}, ensure_ascii=False),
                })
                return

            path = FIELD_TO_SPEC_PATH[field_name]
            value = change["value"]
            patch_changes.append({"path": path, "value": value})

            # 数值字段：同时更新 source/confidence，有 unit 的也更新
            if field_name in FIELD_DEFAULT_UNIT:
                parent = path.rsplit(".", 1)[0]
                extra_patches.append({"path": f"{parent}.source", "value": "user"})
                extra_patches.append({"path": f"{parent}.confidence", "value": 1.0})
                if FIELD_DEFAULT_UNIT[field_name]:
                    extra_patches.append({"path": f"{parent}.unit", "value": FIELD_DEFAULT_UNIT[field_name]})

        # 预处理: 只对被修改的字段，将 None 标量替换为空 dict
        data = state.current_spec.model_dump(mode="json")
        affected_paths = [FIELD_TO_SPEC_PATH[c.get("field", "")] for c in changes]
        _pre_fill_none_scalars(data, affected_paths)

        # 应用补丁
        for change in patch_changes + extra_patches:
            _set_nested(data, change["path"], change["value"])

        try:
            patched = AircraftSpec.model_validate(data)
        except Exception as exc:
            error_msg = f"spec patch 失败: {exc}"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({
                "role": "tool", "tool_call_id": tool_call_id,
                "content": json.dumps({"error": error_msg}, ensure_ascii=False),
            })
            return

        if self._job_runner is None:
            error_msg = "job runner not configured"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({
                "role": "tool", "tool_call_id": tool_call_id,
                "content": json.dumps({"error": error_msg}, ensure_ascii=False),
            })
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
            "role": "tool", "tool_call_id": tool_call_id,
            "content": json.dumps(result, ensure_ascii=False),
        })

    _PART_SET_OPERATIONS: dict[str, dict[str, tuple[str, str, str | None]]] = {
        "part:fuselage": {
            "set_length": ("fuselage", "length", "m"),
            "set_diameter": ("fuselage", "max_diameter", "m"),
        },
        "part:main_wing": {
            "set_span": ("wing", "span", "m"),
            "set_root_chord": ("wing", "root_chord", "m"),
            "set_tip_chord": ("wing", "tip_chord", "m"),
            "set_sweep": ("wing", "sweep", "deg"),
            "set_dihedral": ("wing", "dihedral", "deg"),
        },
        "part:tail": {
            "set_tail_type": ("tail", "type", None),
        },
    }

    # --- engine offset operations ---

    _ENGINE_MOVE_MAP: dict[str, tuple[str, float]] = {
        "move_outboard": ("y_offset", 1.0),
        "move_inboard": ("y_offset", -1.0),
        "move_forward": ("x_offset", 1.0),
        "move_backward": ("x_offset", -1.0),
        "move_up": ("z_offset", 1.0),
        "move_down": ("z_offset", -1.0),
    }

    async def _handle_modify_selected_part(
        self, state: ConversationState, args: dict[str, Any], tool_call_id: str,
    ) -> AsyncIterator[str]:
        if state.current_spec is None:
            error_msg = "没有当前设计，请先使用 generate_design 创建设计"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({
                "role": "tool", "tool_call_id": tool_call_id,
                "content": json.dumps({"error": error_msg}, ensure_ascii=False),
            })
            return

        part_ref = args.get("part_ref", "")
        operation = args.get("operation", "")
        value = args.get("value")

        if not part_ref or not operation or value is None:
            error_msg = "缺少必要参数: part_ref, operation, value"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({
                "role": "tool", "tool_call_id": tool_call_id,
                "content": json.dumps({"error": error_msg}, ensure_ascii=False),
            })
            return

        data = state.current_spec.model_dump(mode="json")

        # --- engine move operations (incremental) ---
        if operation in self._ENGINE_MOVE_MAP:
            if part_ref not in ("part:left_engine", "part:right_engine"):
                error_msg = f"操作 {operation} 仅适用于发动机部件"
                yield _sse_event("error", {"content": error_msg})
                state.messages.append({
                    "role": "tool", "tool_call_id": tool_call_id,
                    "content": json.dumps({"error": error_msg}, ensure_ascii=False),
                })
                return

            offset_field, sign = self._ENGINE_MOVE_MAP[operation]
            new_delta = sign * float(value)
            offset_path = f"engine.{offset_field}"
            _pre_fill_none_scalars(data, [f"{offset_path}.value"])
            # Ensure the offset scalar dict exists even if key is absent
            engine_dict = data.setdefault("engine", {})
            if offset_field not in engine_dict or engine_dict[offset_field] is None:
                engine_dict[offset_field] = {}

            current_val = 0.0
            offset_scalar = engine_dict.get(offset_field)
            if isinstance(offset_scalar, dict) and "value" in offset_scalar:
                current_val = float(offset_scalar["value"])

            new_val = current_val + new_delta
            # Write directly since _set_nested raises on missing keys
            engine_dict.setdefault(offset_field, {})["value"] = new_val
            engine_dict[offset_field]["source"] = "user"
            engine_dict[offset_field]["confidence"] = 1.0
            engine_dict[offset_field]["unit"] = "m"

        # --- set operations (absolute value) ---
        elif part_ref in self._PART_SET_OPERATIONS:
            ops = self._PART_SET_OPERATIONS[part_ref]
            if operation not in ops:
                error_msg = f"部件 {part_ref} 不支持操作 {operation}，可用: {', '.join(ops.keys())}"
                yield _sse_event("error", {"content": error_msg})
                state.messages.append({
                    "role": "tool", "tool_call_id": tool_call_id,
                    "content": json.dumps({"error": error_msg}, ensure_ascii=False),
                })
                return

            section, field_name, default_unit = ops[operation]
            field_path = f"{section}.{field_name}"
            _pre_fill_none_scalars(data, [f"{field_path}.value"])

            section_dict = data.setdefault(section, {})
            if field_name not in section_dict or section_dict[field_name] is None:
                section_dict[field_name] = {}
            scalar_dict = section_dict[field_name]

            if field_name == "type" and section == "tail":
                scalar_dict["value"] = str(value)
            else:
                scalar_dict["value"] = float(value)
            scalar_dict["source"] = "user"
            scalar_dict["confidence"] = 1.0
            if default_unit:
                scalar_dict["unit"] = default_unit

        else:
            error_msg = f"不支持操作的部件: {part_ref}，或未知操作: {operation}"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({
                "role": "tool", "tool_call_id": tool_call_id,
                "content": json.dumps({"error": error_msg}, ensure_ascii=False),
            })
            return

        try:
            patched = AircraftSpec.model_validate(data)
        except Exception as exc:
            error_msg = f"spec patch 失败: {exc}"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({
                "role": "tool", "tool_call_id": tool_call_id,
                "content": json.dumps({"error": error_msg}, ensure_ascii=False),
            })
            return

        if self._job_runner is None:
            error_msg = "job runner not configured"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({
                "role": "tool", "tool_call_id": tool_call_id,
                "content": json.dumps({"error": error_msg}, ensure_ascii=False),
            })
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
            "role": "tool", "tool_call_id": tool_call_id,
            "content": json.dumps(result, ensure_ascii=False),
        })
