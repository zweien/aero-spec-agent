"""Tests for observe_node decorator — structured logging and error handling."""

from __future__ import annotations

import logging

from services.api.app.graph.observe import observe_node


class TestObserveNode:
    def test_decorator_preserves_return_value(self):
        @observe_node("test_node")
        def my_node(state):
            return {"result": 42}

        output = my_node({"input": "data"})
        assert output == {"result": 42}

    def test_decorator_logs_latency(self, caplog):
        @observe_node("latency_test")
        def slow_node(state):
            return {"done": True}

        with caplog.at_level(logging.INFO, logger="aero.graph.observe"):
            slow_node({"x": 1})

        assert any("node_completed" in r.message for r in caplog.records)
        record = next(r for r in caplog.records if "node_completed" in r.message)
        assert record.node == "latency_test"
        assert record.latency_ms >= 0
        assert record.status == "ok"

    def test_decorator_logs_input_keys(self, caplog):
        @observe_node("keys_test")
        def node(state):
            return {"out": 1}

        with caplog.at_level(logging.INFO, logger="aero.graph.observe"):
            node({"alpha": 1, "beta": 2})

        record = next(r for r in caplog.records if "node_completed" in r.message)
        assert record.input_keys == ["alpha", "beta"]
        assert record.output_keys == ["out"]

    def test_decorator_logs_error_on_exception(self, caplog):
        @observe_node("failing_node")
        def bad_node(state):
            raise ValueError("boom")

        with caplog.at_level(logging.ERROR, logger="aero.graph.observe"):
            try:
                bad_node({"x": 1})
            except ValueError:
                pass

        assert any("node_failed" in r.message for r in caplog.records)
        record = next(r for r in caplog.records if "node_failed" in r.message)
        assert record.node == "failing_node"
        assert record.status == "error"

    def test_decorator_does_not_swallow_exceptions(self):
        @observe_node("raise_test")
        def raise_node(state):
            raise RuntimeError("intentional")

        raised = False
        try:
            raise_node({})
        except RuntimeError as e:
            raised = True
            assert str(e) == "intentional"
        assert raised

    def test_decorator_preserves_function_name(self):
        @observe_node("named")
        def original_name(state):
            return {}

        assert original_name.__name__ == "original_name"
