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

SPEC_SCHEMA_EXAMPLE = (
    '\n'
    'schema_version: "0.1"\n'
    'aircraft:\n'
    '  name: my_uav\n'
    '  type: fixed_wing_uav\n'
    '  layout: conventional\n'
    'mission:\n'
    '  cruise_speed: {value: 150, unit: km/h, source: user, confidence: 1.0}\n'
    '  payload: {value: 20, unit: kg, source: user, confidence: 1.0}\n'
    '  priority: {value: endurance, source: user, confidence: 0.9}\n'
    'fuselage:\n'
    '  length: {value: 5.0, unit: m, source: rule_default, confidence: 0.7}\n'
    '  max_diameter: {value: 0.6, unit: m, source: rule_default, confidence: 0.7}\n'
    'wing:\n'
    '  position: {value: high, source: user, confidence: 1.0}\n'
    '  span: {value: 10.0, unit: m, source: user, confidence: 1.0}\n'
    '  root_chord: {value: 1.0, unit: m, source: rule_default, confidence: 0.75}\n'
    '  tip_chord: {value: 0.5, unit: m, source: rule_default, confidence: 0.75}\n'
    '  sweep: {value: 3, unit: deg, source: rule_default, confidence: 0.7}\n'
    '  dihedral: {value: 3, unit: deg, source: rule_default, confidence: 0.7}\n'
    '  airfoil: {value: NACA4412, source: system_default, confidence: 0.6}\n'
    'tail:\n'
    '  type: {value: conventional, source: user, confidence: 1.0}\n'
    'engine:\n'
    '  count: {value: 2, source: user, confidence: 1.0}\n'
    '  position: {value: under_wing, source: inferred, confidence: 0.75}\n'
)

SYSTEM_PROMPT_TEMPLATE = """你是 AeroSpec Agent，一个飞机概念设计助手。

用户用自然语言描述飞机需求，你负责生成或修改 aircraft_spec 参数化设计。

当前设计状态：
%s

规则：
- 只处理固定翼无人机（fixed_wing_uav），常规布局（conventional）
- schema_version 必须是 "0.1"
- aircraft 必须包含 name, type, layout 字段
- 每个数值参数必须包含 value, source, confidence 字段，数值参数额外需要 unit 字段
- 用户明确给出的参数：source=user, confidence=1.0
- 你推断的参数：source=inferred, confidence=0.7-0.9
- 无法确定的参数使用合理默认值：source=rule_default, confidence=0.7
- 新建设计使用 generate_design，修改现有设计使用 modify_design
- 修改时只输出需要变更的字段
- 生成完成后简要解释设计参数和依据

AircraftSpec 完整结构示例（必须严格遵循此结构，不要添加额外字段）：
""" + SPEC_SCHEMA_EXAMPLE

GENERATE_DESIGN_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_design",
        "description": "根据用户需求生成新的飞机设计 spec。当用户描述全新的飞机需求时使用。必须严格遵循 AircraftSpec 结构。",
        "parameters": {
            "type": "object",
            "properties": {
                "schema_version": {
                    "type": "string",
                    "enum": ["0.1"],
                    "description": "固定值 0.1",
                },
                "aircraft": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "飞机名称，用英文下划线命名"},
                        "type": {"type": "string", "enum": ["fixed_wing_uav"]},
                        "layout": {"type": "string", "enum": ["conventional"]},
                    },
                    "required": ["name", "type", "layout"],
                },
                "mission": {
                    "type": "object",
                    "properties": {
                        "cruise_speed": {"$ref": "#/$defs/numeric_scalar"},
                        "payload": {"$ref": "#/$defs/numeric_scalar"},
                        "priority": {"$ref": "#/$defs/text_scalar"},
                    },
                },
                "fuselage": {
                    "type": "object",
                    "properties": {
                        "length": {"$ref": "#/$defs/numeric_scalar"},
                        "max_diameter": {"$ref": "#/$defs/numeric_scalar"},
                    },
                    "required": ["length"],
                },
                "wing": {
                    "type": "object",
                    "properties": {
                        "position": {"$ref": "#/$defs/text_scalar"},
                        "span": {"$ref": "#/$defs/numeric_scalar"},
                        "root_chord": {"$ref": "#/$defs/numeric_scalar"},
                        "tip_chord": {"$ref": "#/$defs/numeric_scalar"},
                        "sweep": {"$ref": "#/$defs/numeric_scalar"},
                        "dihedral": {"$ref": "#/$defs/numeric_scalar"},
                        "airfoil": {"$ref": "#/$defs/text_scalar"},
                    },
                    "required": ["position", "span", "root_chord", "tip_chord"],
                },
                "tail": {
                    "type": "object",
                    "properties": {
                        "type": {"$ref": "#/$defs/text_scalar"},
                    },
                    "required": ["type"],
                },
                "engine": {
                    "type": "object",
                    "properties": {
                        "count": {"$ref": "#/$defs/integer_scalar"},
                        "position": {"$ref": "#/$defs/text_scalar"},
                    },
                    "required": ["count"],
                },
            },
            "required": ["schema_version", "aircraft", "fuselage", "wing", "tail", "engine"],
            "$defs": {
                "numeric_scalar": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number"},
                        "unit": {"type": "string"},
                        "source": {"type": "string", "enum": ["user", "inferred", "rule_default", "system_default"]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "reason": {"type": "string"},
                    },
                    "required": ["value", "source", "confidence"],
                },
                "integer_scalar": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "integer"},
                        "source": {"type": "string", "enum": ["user", "inferred", "rule_default", "system_default"]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "reason": {"type": "string"},
                    },
                    "required": ["value", "source", "confidence"],
                },
                "text_scalar": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "source": {"type": "string", "enum": ["user", "inferred", "rule_default", "system_default"]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "reason": {"type": "string"},
                    },
                    "required": ["value", "source", "confidence"],
                },
            },
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
        self._model = os.getenv("OPENAI_MODEL", "deepseek-chat")
        self._client: OpenAI | None = None
        self._job_runner = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            api_key = os.getenv("OPENAI_API_KEY", "")
            base_url = os.getenv("OPENAI_BASE_URL")
            saved_proxy = {}
            for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
                if val := os.environ.pop(key, None):
                    saved_proxy[key] = val
            try:
                self._client = OpenAI(api_key=api_key, base_url=base_url)
            finally:
                os.environ.update(saved_proxy)
        return self._client

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

        response = self._get_client().chat.completions.create(
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

        second_response = self._get_client().chat.completions.create(
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

    async def _handle_generate_design(self, state: ConversationState, args: dict[str, Any], tool_call_id: str) -> AsyncIterator[str]:
        try:
            spec_data = args.get("spec", args)
            if "schema_version" in spec_data and isinstance(spec_data["schema_version"], str):
                spec_data["schema_version"] = spec_data["schema_version"].strip('"')
            spec = AircraftSpec.model_validate(spec_data)
        except Exception as exc:
            error_msg = f"spec 校验失败: {exc}"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": json.dumps({"error": error_msg}, ensure_ascii=False)})
            return

        if self._job_runner is None:
            error_msg = "job runner not configured"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": json.dumps({"error": error_msg}, ensure_ascii=False)})
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
            "tool_call_id": tool_call_id,
            "content": json.dumps(result, ensure_ascii=False),
        })

    async def _handle_modify_design(self, state: ConversationState, args: dict[str, Any], tool_call_id: str) -> AsyncIterator[str]:
        if state.current_spec is None:
            error_msg = "没有当前设计，请先使用 generate_design 创建设计"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": json.dumps({"error": error_msg}, ensure_ascii=False)})
            return

        changes = args.get("changes", [])
        if not changes:
            error_msg = "changes 不能为空"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": json.dumps({"error": error_msg}, ensure_ascii=False)})
            return

        try:
            patched = apply_patch(state.current_spec, changes)
        except Exception as exc:
            error_msg = f"spec patch 失败: {exc}"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": json.dumps({"error": error_msg}, ensure_ascii=False)})
            return

        if self._job_runner is None:
            error_msg = "job runner not configured"
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": json.dumps({"error": error_msg}, ensure_ascii=False)})
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
            "tool_call_id": tool_call_id,
            "content": json.dumps(result, ensure_ascii=False),
        })
