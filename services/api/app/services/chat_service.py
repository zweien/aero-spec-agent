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
    "cruise_speed": "km/h", "payload": "kg",
}

# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def _flat_args_to_spec(args: dict[str, Any]) -> AircraftSpec:
    """Convert flat generate_design args to full AircraftSpec with metadata."""
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
        elif scalar_type == "text":
            target[last_key] = {"value": str(value), "source": "user", "confidence": 1.0}
        elif scalar_type == "integer":
            target[last_key] = {"value": int(value), "source": "user", "confidence": 1.0}
        else:
            scalar: dict[str, Any] = {"value": float(value), "source": "user", "confidence": 1.0}
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

SYSTEM_PROMPT_TEMPLATE = """你是 AeroSpec Agent，一个飞机概念设计助手。

用户用自然语言描述飞机需求，你负责生成或修改参数化设计。

当前设计状态：
%s

规则：
- 只处理固定翼无人机（fixed_wing_uav），常规布局（conventional）
- 新建设计使用 generate_design，修改现有设计使用 modify_design
- 用户明确给出的参数直接填入，其余参数根据航空工程经验推断合理默认值
- 生成完成后简要解释设计参数和依据
"""


@dataclass
class ConversationState:
    conversation_id: str
    design_id: str
    messages: list[dict[str, str]] = field(default_factory=list)
    current_spec: AircraftSpec | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "design_id": self.design_id,
            "messages": self.messages,
            "current_spec": self.current_spec.model_dump(mode="json") if self.current_spec else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversationState:
        spec_data = data.get("current_spec")
        return cls(
            conversation_id=data["conversation_id"],
            design_id=data["design_id"],
            messages=data.get("messages", []),
            current_spec=AircraftSpec.model_validate(spec_data) if spec_data else None,
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
        return [GENERATE_DESIGN_TOOL, MODIFY_DESIGN_TOOL]

    def _build_system_prompt(self, state: ConversationState) -> str:
        if state.current_spec is not None:
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                dump_aircraft_spec(state.current_spec, Path(f.name))
                spec_yaml = Path(f.name).read_text(encoding="utf-8")
            Path(f.name).unlink(missing_ok=True)
        else:
            spec_yaml = "尚无设计"
        return SYSTEM_PROMPT_TEMPLATE % spec_yaml

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
            else:
                state.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps({"error": f"unknown tool: {tool_name}"}, ensure_ascii=False),
                })

        second_response = await self._get_client().chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system_prompt}] + state.messages,
            stream=True,
        )

        final_content = ""
        async for chunk in second_response:
            choice = chunk.choices[0] if chunk.choices else None
            if choice and choice.delta and choice.delta.content:
                final_content += choice.delta.content
                yield _sse_event("message", choice.delta.content)

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
