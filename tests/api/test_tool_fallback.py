"""Tests for no-tool-call fallback intent detection."""

import os

import pytest

from services.api.app.services.tool_fallback import (
    ToolFallbackIntent,
    build_generate_design_args,
    build_modify_design_args,
    build_modify_selected_part_args,
    detect_generation_intent,
    is_fallback_enabled,
)


# ---------------------------------------------------------------------------
# generate_design positive cases
# ---------------------------------------------------------------------------


class TestDetectGenerateIntent:
    def test_simple_chinese(self):
        intent = detect_generation_intent("设计一架翼展12米的固定翼无人机")
        assert intent is not None
        assert intent.tool_name == "generate_design"
        assert intent.confidence >= 0.6

    def test_with_dimensions(self):
        intent = detect_generation_intent("帮我生成一架翼展15米 双发 上单翼的无人机")
        assert intent is not None
        assert intent.tool_name == "generate_design"
        assert intent.confidence >= 0.8
        args = intent.args
        assert args["wing_span"] == 15.0
        assert args["engine_count"] == 2

    def test_with_layout_keywords(self):
        intent = detect_generation_intent("设计一架长航时固定翼飞行器")
        assert intent is not None
        assert intent.tool_name == "generate_design"

    def test_english_keywords(self):
        intent = detect_generation_intent("design a fixed wing UAV")
        assert intent is not None
        assert intent.tool_name == "generate_design"

    def test_assistant_text_boosts_confidence(self):
        intent = detect_generation_intent(
            "设计一架无人机",
            assistant_text="好的，我来生成翼展12米的参数。",
        )
        assert intent is not None
        assert intent.confidence >= 0.7

    def test_no_current_design(self):
        intent = detect_generation_intent("设计一架无人机", has_current_design=False)
        assert intent is not None
        assert intent.tool_name == "generate_design"

    def test_with_current_design_still_generates_if_keyword(self):
        intent = detect_generation_intent("设计一架新的无人机", has_current_design=True)
        assert intent is not None
        assert intent.tool_name == "generate_design"


# ---------------------------------------------------------------------------
# modify_design positive cases
# ---------------------------------------------------------------------------


class TestDetectModifyIntent:
    def test_modify_with_current_design(self):
        intent = detect_generation_intent(
            "把翼展改为15米",
            has_current_design=True,
        )
        assert intent is not None
        assert intent.tool_name == "modify_design"

    def test_optimize_layout(self):
        intent = detect_generation_intent(
            "优化为长航时布局",
            has_current_design=True,
        )
        assert intent is not None
        assert intent.tool_name == "modify_design"

    def test_modify_no_trigger_without_design(self):
        intent = detect_generation_intent(
            "把翼展改为15米",
            has_current_design=False,
        )
        # Should NOT trigger modify_design without current design;
        # might trigger generate_design if keywords overlap
        if intent is not None:
            assert intent.tool_name != "modify_design"


# ---------------------------------------------------------------------------
# modify_selected_part positive cases
# ---------------------------------------------------------------------------


class TestDetectSelectedPartIntent:
    def test_selected_part_modify(self):
        intent = detect_generation_intent(
            "把这个机翼加长",
            selected_part="part:wing",
        )
        assert intent is not None
        assert intent.tool_name == "modify_selected_part"

    def test_selected_part_with_number(self):
        intent = detect_generation_intent(
            "选中部件长度改为5米",
            selected_part="part:fuselage",
        )
        assert intent is not None
        assert intent.tool_name == "modify_selected_part"

    def test_no_trigger_without_selected_part(self):
        intent = detect_generation_intent("加长2米")
        # Without selected_part and has_current_design=False, no trigger expected
        assert intent is None or intent.tool_name != "modify_selected_part"


# ---------------------------------------------------------------------------
# Negative cases (must return None)
# ---------------------------------------------------------------------------


class TestNegativeCases:
    @pytest.mark.parametrize(
        "message",
        [
            "什么是展弦比？",
            "固定翼无人机有哪些布局？",
            "请解释一下 OpenVSP",
            "刚才的设计有什么问题？",
            "不要生成，只给我讲讲设计思路",
            "帮我写一段产品介绍",
            "导出报告",
            "查看模型",
            "好",
            "ok",
            "是的",
            "告诉我长航时无人机的特点",
        ],
    )
    def test_negative_messages(self, message):
        intent = detect_generation_intent(message)
        assert intent is None, f"Expected None for '{message}', got {intent}"

    def test_negative_short_question(self):
        intent = detect_generation_intent("为什么？")
        assert intent is None

    def test_negative_export_command(self):
        intent = detect_generation_intent("导出当前设计报告")
        assert intent is None

    def test_negative_view_command(self):
        intent = detect_generation_intent("查看模型")
        assert intent is None


# ---------------------------------------------------------------------------
# Args construction
# ---------------------------------------------------------------------------


class TestBuildGenerateArgs:
    def test_extracts_wing_span(self):
        args = build_generate_design_args("翼展12米 双发 上单翼")
        assert args["wing_span"] == 12.0

    def test_extracts_fuselage_length(self):
        args = build_generate_design_args("机身长度8米的无人机")
        assert args["fuselage_length"] == 8.0

    def test_extracts_engine_count(self):
        args = build_generate_design_args("双发固定翼")
        assert args["engine_count"] == 2

    def test_extracts_wing_position(self):
        args = build_generate_design_args("上单翼无人机")
        assert args["wing_position"] == "high"

    def test_extracts_priority(self):
        args = build_generate_design_args("长航时飞行器")
        assert args["priority"] == "endurance"

    def test_no_dimensions_returns_minimal(self):
        args = build_generate_design_args("设计一架固定翼")
        assert args["name"] == "fallback_uav"
        assert args["source"] == "no_tool_call_fallback"

    def test_english_dimensions(self):
        args = build_generate_design_args("wingspan 10m fuselage 6m")
        assert args.get("wing_span") == 10.0
        assert args.get("fuselage_length") == 6.0


class TestBuildModifyArgs:
    def test_extracts_changes(self):
        args = build_modify_design_args("把翼展改为15米")
        assert len(args["changes"]) >= 1
        assert args["changes"][0]["field"] == "wing_span"
        assert args["changes"][0]["value"] == 15.0

    def test_extracts_fuselage_change(self):
        args = build_modify_design_args("机身长度改为8米")
        assert len(args["changes"]) >= 1
        assert args["changes"][0]["field"] == "fuselage_length"

    def test_returns_instruction(self):
        args = build_modify_design_args("优化为长航时布局")
        assert args["instruction"] == "优化为长航时布局"
        assert args["source"] == "no_tool_call_fallback"


class TestBuildSelectedPartArgs:
    def test_increase_operation(self):
        args = build_modify_selected_part_args("part:wing", "把这个机翼加长2米")
        assert args["part_ref"] == "wing"
        assert args["operation"] == "increase"
        assert args["value"] == 2.0

    def test_decrease_operation(self):
        args = build_modify_selected_part_args("part:fuselage", "缩短机身")
        assert args["operation"] == "decrease"

    def test_set_operation(self):
        args = build_modify_selected_part_args("part:wing", "把翼展改为10米")
        assert args["operation"] == "set"
        assert args["value"] == 10.0


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestConfig:
    def test_fallback_enabled_default(self):
        assert is_fallback_enabled() is True

    def test_fallback_disabled(self, monkeypatch):
        monkeypatch.setenv("NO_TOOL_CALL_FALLBACK", "false")
        assert is_fallback_enabled() is False

    def test_confidence_threshold(self, monkeypatch):
        monkeypatch.setenv("NO_TOOL_CALL_FALLBACK_MIN_CONFIDENCE", "0.95")
        intent = detect_generation_intent("设计一架无人机")
        assert intent is None  # 0.7 < 0.95

    def test_confidence_threshold_allows_high(self, monkeypatch):
        monkeypatch.setenv("NO_TOOL_CALL_FALLBACK_MIN_CONFIDENCE", "0.8")
        intent = detect_generation_intent("设计一架翼展12米的固定翼无人机")
        assert intent is not None  # 0.85 >= 0.8
