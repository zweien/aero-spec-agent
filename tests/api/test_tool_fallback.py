"""Tests for no-tool-call fallback args-builders.

Intent classification is tested in test_intent_classifier.py. This file tests
only the args-builders (build_*_args / build_args_for_intent), which extract
dimensions and operations from a message once the intent is known.
"""

import pytest

from services.api.app.services.tool_fallback import (
    build_args_for_intent,
    build_generate_design_args,
    build_modify_design_args,
    build_modify_selected_part_args,
    is_fallback_enabled,
)


# ---------------------------------------------------------------------------
# build_generate_design_args
# ---------------------------------------------------------------------------


class TestBuildGenerateArgs:
    def test_extracts_wing_span(self):
        args = build_generate_design_args("设计一架翼展15米的无人机")
        assert args["wing_span"] == 15.0

    def test_extracts_fuselage_length(self):
        args = build_generate_design_args("机身长度6米的无人机")
        assert args["fuselage_length"] == 6.0

    def test_extracts_engine_count(self):
        args = build_generate_design_args("设计一架双发的无人机")
        assert args["engine_count"] == 2

    def test_extracts_wing_position(self):
        args = build_generate_design_args("设计一架上单翼无人机")
        assert args["wing_position"] == "high"

    def test_extracts_priority(self):
        args = build_generate_design_args("设计一架长航时无人机")
        assert args["priority"] == "endurance"

    def test_no_dimensions_returns_minimal(self):
        args = build_generate_design_args("设计一架无人机")
        assert args["name"] == "fallback_uav"
        assert args["source"] == "no_tool_call_fallback"
        assert "inferred_fields" in args

    def test_english_dimensions(self):
        args = build_generate_design_args("design a uav with wingspan 12 m twin engine")
        assert args["wing_span"] == 12.0
        assert args["engine_count"] == 2


# ---------------------------------------------------------------------------
# build_modify_design_args
# ---------------------------------------------------------------------------


class TestBuildModifyArgs:
    def test_extracts_changes(self):
        args = build_modify_design_args("把翼展改为10米")
        assert any(c["field"] == "wing_span" and c["value"] == 10.0 for c in args["changes"])

    def test_extracts_fuselage_change(self):
        args = build_modify_design_args("机身长度改为5米")
        assert any(c["field"] == "fuselage_length" and c["value"] == 5.0 for c in args["changes"])

    def test_returns_instruction(self):
        msg = "把翼展改为10米"
        args = build_modify_design_args(msg)
        assert args["instruction"] == msg
        assert args["source"] == "no_tool_call_fallback"


# ---------------------------------------------------------------------------
# build_modify_selected_part_args
# ---------------------------------------------------------------------------


class TestBuildSelectedPartArgs:
    def test_increase_operation(self):
        args = build_modify_selected_part_args("part:fuselage", "加长2米")
        assert args["operation"] == "increase"
        assert args["value"] == 2.0
        assert args["part_ref"] == "fuselage"

    def test_decrease_operation(self):
        args = build_modify_selected_part_args("part:fuselage", "缩短0.5米")
        assert args["operation"] == "decrease"

    def test_set_operation(self):
        args = build_modify_selected_part_args("part:fuselage", "改为6米")
        assert args["operation"] == "set"


# ---------------------------------------------------------------------------
# build_args_for_intent dispatch
# ---------------------------------------------------------------------------


class TestBuildArgsForIntent:
    def test_generate_dispatch(self):
        args = build_args_for_intent("generate_design", "翼展8米")
        assert "name" in args

    def test_modify_dispatch(self):
        args = build_args_for_intent("modify_design", "翼展改为9米")
        assert "changes" in args

    def test_selected_part_dispatch(self):
        args = build_args_for_intent(
            "modify_selected_part", "加长2米", selected_part="part:fuselage"
        )
        assert args["part_ref"] == "fuselage"

    def test_unknown_intent_raises(self):
        with pytest.raises(ValueError):
            build_args_for_intent("conversation", "hello")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestConfig:
    def test_fallback_enabled_default(self):
        assert is_fallback_enabled() is True

    def test_fallback_disabled(self, monkeypatch):
        monkeypatch.setenv("NO_TOOL_CALL_FALLBACK", "false")
        assert is_fallback_enabled() is False
