from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from services.api.app.graph.design_graph import classify_message_intent
from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.chat_tools import (
    FIELD_DEFAULT_UNIT,
    FIELD_TO_SPEC_PATH,
    FLAT_FIELD_DEFS,
    GENERATE_DESIGN_TOOL,
    MODIFY_DESIGN_TOOL,
    MODIFY_SELECTED_PART_TOOL,
    SUPPORTED_FIELD_VALUES,
)
from services.api.app.services.selected_part_modifier import (
    SelectedPartPatchError,
    apply_selected_part_patch,
)
from services.api.app.services.spec_io import dump_aircraft_spec
from services.api.app.services.spec_patch import _set_nested

logger = logging.getLogger(__name__)
_CHAT_GENERATION_EXECUTOR = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="chat-generation",
)

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


def _normalize_modify_field_name(field_name: str) -> str | None:
    if field_name in FIELD_TO_SPEC_PATH:
        return field_name
    candidates = [
        known
        for known in FIELD_TO_SPEC_PATH
        if _is_single_edit_apart(field_name, known)
    ]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _is_single_edit_apart(value: str, target: str) -> bool:
    if value == target:
        return True
    if abs(len(value) - len(target)) > 1:
        return False

    if len(value) == len(target):
        return sum(left != right for left, right in zip(value, target)) == 1

    shorter, longer = (value, target) if len(value) < len(target) else (target, value)
    i = j = edits = 0
    while i < len(shorter) and j < len(longer):
        if shorter[i] == longer[j]:
            i += 1
            j += 1
            continue
        edits += 1
        if edits > 1:
            return False
        j += 1
    return True


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


SYSTEM_PROMPT_TEMPLATE = """你是 AeroSpec Agent，一个飞机概念设计助手。

用户用自然语言描述飞机需求，你负责生成或修改参数化设计。

当前设计状态：
%s

当前选中对象：
{selected_refs}

规则：
- 只处理固定翼无人机（fixed_wing_uav），常规布局（conventional）
- 新建设计使用 generate_design
- 修改现有设计使用 modify_design（一次性改多个参数时使用）
- 当「当前选中对象」非空时，用户的修改请求应优先使用 modify_selected_part
  - 例如选中了 part:fuselage，用户说"加长2米"，应调用 modify_selected_part(part_ref="part:fuselage", operation="increase_length", value=2)
  - 不要使用 modify_design 来修改选中部件的参数
- 当用户说"加长/增加/扩大/提高/往外/向前"等相对变化时，优先使用 increase_*/decrease_* 或 move_* 操作
- 当用户说"改成/设置为/设为/变为"时，使用 set_* 绝对值操作
- 示例：选中 part:fuselage，用户说"机身长度改为9米"，调用 modify_selected_part(part_ref="part:fuselage", operation="set_length", value=9)
- 示例：选中 part:right_engine，用户说"向外移动0.5米"，调用 modify_selected_part(part_ref="part:right_engine", operation="move_outboard", value=0.5)
- modify_selected_part 支持的操作：
  - 机身(part:fuselage): set_length/increase_length/decrease_length(m), set_diameter/increase_diameter/decrease_diameter(m)
  - 机翼(part:main_wing): set/increase/decrease span/root_chord/tip_chord(m), sweep/dihedral(deg)
  - 尾翼(part:tail): set_tail_type(当前仅 conventional)
  - 发动机(part:left_engine/part:right_engine): move_outboard/inboard/forward/backward/up/down(增量/m)
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


def _chat_generation_mode() -> str:
    mode = os.getenv("CHAT_GENERATION_MODE", "sync").strip().lower()
    if mode == "async":
        return "async"
    return "sync"


class ChatService:
    def __init__(self, storage_root: str | Path | None = None) -> None:
        self._conversations: dict[str, ConversationState] = {}
        self._model = os.getenv("OPENAI_MODEL", "deepseek-chat")
        self._client: AsyncOpenAI | None = None
        self._job_runner = None
        self._storage_root = Path(storage_root) if storage_root else Path("storage")
        self._background_generation_tasks: set[Future] = set()

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

    def _schedule_job_generation(self, job: Any, spec: AircraftSpec) -> None:
        future = _CHAT_GENERATION_EXECUTOR.submit(self._job_runner.run_job_generation, job, spec)
        self._background_generation_tasks.add(future)

        def _cleanup(done_task: Future) -> None:
            self._background_generation_tasks.discard(done_task)
            try:
                done_task.result()
            except Exception:
                logger.exception("background chat generation task failed")

        future.add_done_callback(_cleanup)

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
        background_tasks: Any | None = None,
    ) -> AsyncIterator[str]:
        state = self.get_or_create_state(conversation_id)
        if selected_refs is not None:
            state.selected_refs = list(selected_refs)
        shadow_intent = classify_message_intent(
            message,
            selected_refs=state.selected_refs,
            has_current_spec=state.current_spec is not None,
        )
        logger.debug(
            "chat shadow_intent=%s conversation_id=%s selected_refs=%s",
            shadow_intent,
            conversation_id,
            state.selected_refs,
        )
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
            logger.debug(
                "chat shadow_intent_actual_tool=%s",
                json.dumps(
                    {
                        "message": message,
                        "selected_refs": state.selected_refs,
                        "shadow_intent": shadow_intent,
                        "actual_tool": tool_name,
                    },
                    ensure_ascii=False,
                ),
            )

            try:
                tool_args = json.loads(tool_args_str)
            except json.JSONDecodeError:
                tool_result = json.dumps({"error": "invalid JSON arguments"}, ensure_ascii=False)
                state.messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": tool_result})
                continue

            if tool_name == "generate_design":
                async for event in self._handle_generate_design(
                    state,
                    tool_args,
                    tool_call_id,
                    background_tasks=background_tasks,
                ):
                    yield event
            elif tool_name == "modify_design":
                async for event in self._handle_modify_design(
                    state,
                    tool_args,
                    tool_call_id,
                    background_tasks=background_tasks,
                ):
                    yield event
            elif tool_name == "modify_selected_part":
                async for event in self._handle_modify_selected_part(
                    state,
                    tool_args,
                    tool_call_id,
                    background_tasks=background_tasks,
                ):
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
        self,
        state: ConversationState,
        args: dict[str, Any],
        tool_call_id: str,
        background_tasks: Any | None = None,
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

        if _chat_generation_mode() == "async":
            job = self._job_runner.create_job(design_id=state.design_id)
            state.current_spec = spec
            result = _job_result(job)
            yield _sse_event("generation_started", result)
            self._schedule_job_generation(job, spec)
        else:
            job = self._job_runner.create_job(design_id=state.design_id)
            yield _sse_event("generation_started", _job_result(job))
            self._job_runner.run_job_generation(job, spec)
            state.current_spec = spec
            result = _job_result(job)
            yield _sse_event("generation_complete", result)

        state.messages.append({
            "role": "tool", "tool_call_id": tool_call_id,
            "content": json.dumps(result, ensure_ascii=False),
        })

    async def _handle_modify_design(
        self,
        state: ConversationState,
        args: dict[str, Any],
        tool_call_id: str,
        background_tasks: Any | None = None,
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
        affected_paths: list[str] = []
        for change in changes:
            requested_field_name = str(change.get("field", ""))
            field_name = _normalize_modify_field_name(requested_field_name)
            if field_name is None:
                error_msg = f"未知字段: {requested_field_name}，可选: {', '.join(FIELD_TO_SPEC_PATH.keys())}"
                yield _sse_event("error", {"content": error_msg})
                state.messages.append({
                    "role": "tool", "tool_call_id": tool_call_id,
                    "content": json.dumps({"error": error_msg}, ensure_ascii=False),
                })
                return

            if field_name in SUPPORTED_FIELD_VALUES:
                supported_values = SUPPORTED_FIELD_VALUES[field_name]
                value_text = str(change.get("value", ""))
                if value_text not in supported_values:
                    error_msg = (
                        f"字段 {field_name} 当前仅支持: {', '.join(sorted(supported_values))}，"
                        f"已拒绝写入 {value_text}"
                    )
                    yield _sse_event("error", {"content": error_msg})
                    state.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps({"error": error_msg}, ensure_ascii=False),
                    })
                    return

            path = FIELD_TO_SPEC_PATH[field_name]
            value = change["value"]
            patch_changes.append({"path": path, "value": value})
            affected_paths.append(path)

            # 数值字段：同时更新 source/confidence，有 unit 的也更新
            if field_name in FIELD_DEFAULT_UNIT:
                parent = path.rsplit(".", 1)[0]
                extra_patches.append({"path": f"{parent}.source", "value": "user"})
                extra_patches.append({"path": f"{parent}.confidence", "value": 1.0})
                if FIELD_DEFAULT_UNIT[field_name]:
                    extra_patches.append({"path": f"{parent}.unit", "value": FIELD_DEFAULT_UNIT[field_name]})

        # 预处理: 只对被修改的字段，将 None 标量替换为空 dict
        data = state.current_spec.model_dump(mode="json")
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

        if _chat_generation_mode() == "async":
            job = self._job_runner.create_job(design_id=state.design_id)
            state.current_spec = patched
            result = _job_result(job)
            yield _sse_event("generation_started", result)
            self._schedule_job_generation(job, patched)
        else:
            job = self._job_runner.create_job(design_id=state.design_id)
            yield _sse_event("generation_started", _job_result(job))
            self._job_runner.run_job_generation(job, patched)
            state.current_spec = patched
            result = _job_result(job)
            yield _sse_event("generation_complete", result)

        state.messages.append({
            "role": "tool", "tool_call_id": tool_call_id,
            "content": json.dumps(result, ensure_ascii=False),
        })

    async def _handle_modify_selected_part(
        self,
        state: ConversationState,
        args: dict[str, Any],
        tool_call_id: str,
        background_tasks: Any | None = None,
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

        try:
            patched = apply_selected_part_patch(
                state.current_spec,
                state.selected_refs,
                part_ref,
                operation,
                value,
            )
        except SelectedPartPatchError as exc:
            error_msg = str(exc)
            yield _sse_event("error", {"content": error_msg})
            state.messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
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

        if _chat_generation_mode() == "async":
            job = self._job_runner.create_job(design_id=state.design_id)
            state.current_spec = patched
            result = _job_result(job, message=f"已基于选中对象 {part_ref} 完成修改。")
            yield _sse_event("generation_started", result)
            self._schedule_job_generation(job, patched)
        else:
            job = self._job_runner.create_job(design_id=state.design_id)
            yield _sse_event("generation_started", _job_result(job))
            self._job_runner.run_job_generation(job, patched)
            state.current_spec = patched
            result = _job_result(job, message=f"已基于选中对象 {part_ref} 完成修改。")
            yield _sse_event("generation_complete", result)

        state.messages.append({
            "role": "tool", "tool_call_id": tool_call_id,
            "content": json.dumps(result, ensure_ascii=False),
        })


def _job_result(job: Any, message: str | None = None) -> dict[str, Any]:
    result = {
        "job_id": job.id,
        "status": job.status,
        "version_no": job.version_no,
        "design_id": job.design_id,
        "files": list(job.files.keys()),
        "error_message": job.error_message,
        "version_status": getattr(job, "version_status", "pending"),
        "created_at": getattr(job, "created_at", ""),
        "updated_at": getattr(job, "updated_at", ""),
        "duration_ms": getattr(job, "duration_ms", None),
    }
    if message:
        result["message"] = message
    return result
