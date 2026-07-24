"""Tests for the unified intent classifier (graph/nodes/classify_intent._classify).

One place answers "what does this message want to do" — these tests cover all
four intents (generate/modify/modify_selected_part/conversation), the confidence
threshold, and negative (informational) filtering.
"""

import pytest

from services.api.app.graph.nodes.classify_intent import _classify


# ---------------------------------------------------------------------------
# generate_design
# ---------------------------------------------------------------------------


class TestClassifyGenerate:
    def test_simple_chinese(self):
        r = _classify("设计一架翼展12米的固定翼无人机")
        assert r is not None
        assert r.intent == "generate_design"
        assert r.confidence >= 0.6

    def test_with_dimensions(self):
        r = _classify("帮我生成一架翼展15米 双发 上单翼的无人机")
        assert r is not None
        assert r.intent == "generate_design"
        assert r.confidence >= 0.8

    def test_english_keywords(self):
        r = _classify("design a fixed wing uav")
        assert r is not None
        assert r.intent == "generate_design"

    def test_assistant_text_boosts_confidence(self):
        r_no = _classify("设计一架无人机", assistant_text=None)
        r_yes = _classify("设计一架无人机", assistant_text="翼展参数是10米")
        assert r_yes is not None
        assert r_yes.confidence >= r_no.confidence

    def test_no_current_design_still_generates(self):
        r = _classify("设计一架无人机", has_spec=False)
        assert r is not None
        assert r.intent == "generate_design"


# ---------------------------------------------------------------------------
# modify_design
# ---------------------------------------------------------------------------


class TestClassifyModify:
    def test_modify_with_current_design(self):
        r = _classify("把翼展改为10米", has_spec=True)
        assert r is not None
        assert r.intent == "modify_design"

    def test_optimize_layout(self):
        r = _classify("优化机翼参数", has_spec=True)
        assert r is not None
        assert r.intent == "modify_design"

    def test_modify_no_trigger_without_design(self):
        # Without an existing spec, modify verbs fall through to generate only
        # if a generate keyword is present; here there is none → None.
        r = _classify("把翼展改为10米", has_spec=False)
        assert r is None


# ---------------------------------------------------------------------------
# modify_selected_part
# ---------------------------------------------------------------------------


class TestClassifySelectedPart:
    def test_selected_part_with_action(self):
        r = _classify("加长2米", selected_refs=["part:fuselage"], has_spec=True)
        assert r is not None
        assert r.intent == "modify_selected_part"

    def test_selected_part_reference(self):
        r = _classify("这个加长一点", selected_refs=["part:fuselage"], has_spec=True)
        assert r is not None
        assert r.intent == "modify_selected_part"

    def test_no_trigger_without_selected_part(self):
        # No part selected: a modify verb falls through to modify_design (not
        # modify_selected_part), since modify_selected_part requires a selection.
        r = _classify("加长2米", selected_refs=None, has_spec=True)
        assert r is None or r.intent != "modify_selected_part"


# ---------------------------------------------------------------------------
# Negative / conversation
# ---------------------------------------------------------------------------


class TestNegativeCases:
    @pytest.mark.parametrize("message", [
        "什么是升阻比",
        "解释一下翼型",
        "无人机有哪些类型",
    ])
    def test_informational_returns_none(self, message):
        assert _classify(message) is None

    def test_negative_export_command(self):
        assert _classify("导出报告") is None

    def test_negative_view_command(self):
        assert _classify("查看模型") is None

    def test_negative_short_question(self):
        assert _classify("为什么？") is None

    def test_too_short(self):
        assert _classify("好") is None


# ---------------------------------------------------------------------------
# Confidence threshold
# ---------------------------------------------------------------------------


class TestConfidenceThreshold:
    def test_threshold_filters_low_confidence(self, monkeypatch):
        monkeypatch.setenv("NO_TOOL_CALL_FALLBACK_MIN_CONFIDENCE", "0.95")
        # "设计一架无人机" → 0.7 < 0.95 → filtered.
        assert _classify("设计一架无人机") is None

    def test_threshold_allows_high_confidence(self, monkeypatch):
        monkeypatch.setenv("NO_TOOL_CALL_FALLBACK_MIN_CONFIDENCE", "0.8")
        # "设计一架翼展12米的固定翼无人机" → 0.85 >= 0.8 → passes.
        r = _classify("设计一架翼展12米的固定翼无人机")
        assert r is not None
        assert r.intent == "generate_design"
