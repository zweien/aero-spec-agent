"""Tests for graph runtime metrics collection."""

from __future__ import annotations

import logging

from services.api.app.graph.metrics import (
    MetricsCollector,
    MetricSnapshot,
    get_metrics_collector,
    reset_metrics_collector,
)


class TestMetricsCollector:
    def test_record_graph_request(self):
        mc = MetricsCollector()
        mc.record_graph_request()
        snap = mc.snapshot()
        assert snap.graph_requests == 1
        assert snap.total_requests == 1

    def test_record_fallback(self):
        mc = MetricsCollector()
        mc.record_fallback("partial")
        snap = mc.snapshot()
        assert snap.fallback_requests == 1
        assert snap.fallback_rate == 1.0

    def test_fallback_rate_calculation(self):
        mc = MetricsCollector()
        mc.record_graph_request()
        mc.record_graph_request()
        mc.record_fallback("partial")
        snap = mc.snapshot()
        assert snap.total_requests == 3
        assert snap.fallback_rate == 1 / 3

    def test_record_graph_latency(self):
        mc = MetricsCollector()
        mc.record_graph_latency("enqueue_job", 45.2)
        mc.record_graph_latency("enqueue_job", 30.1)
        snap = mc.snapshot()
        assert len(snap.node_latencies["enqueue_job"]) == 2

    def test_record_deep_design(self):
        mc = MetricsCollector()
        mc.record_deep_design(duration_ms=5000, status="completed", variants=3, succeeded=2)
        snap = mc.snapshot()
        assert snap.deep_design_runs == 1
        assert snap.total_variants == 3
        assert snap.succeeded_variants == 2
        assert snap.variant_success_rate == 2 / 3

    def test_prometheus_format(self):
        mc = MetricsCollector()
        mc.record_graph_request()
        mc.record_graph_request()
        mc.record_fallback("partial")
        mc.record_deep_design(duration_ms=1000, status="completed", variants=2, succeeded=2)
        mc.record_graph_latency("enqueue_job", 50.0)

        output = mc.snapshot().to_prometheus()
        assert "graph_requests_total 2" in output
        assert "graph_fallbacks_total 1" in output
        assert "deep_design_runs_total 1" in output
        assert "variant_success_rate" in output
        assert 'node="enqueue_job"' in output

    def test_snapshot_is_copy(self):
        mc = MetricsCollector()
        mc.record_graph_request()
        snap1 = mc.snapshot()
        mc.record_graph_request()
        snap2 = mc.snapshot()
        assert snap1.graph_requests == 1
        assert snap2.graph_requests == 2

    def test_empty_metrics(self):
        mc = MetricsCollector()
        snap = mc.snapshot()
        assert snap.fallback_rate == 0.0
        assert snap.variant_success_rate == 0.0
        prom = snap.to_prometheus()
        assert "graph_requests_total 0" in prom

    def test_singleton_collector(self):
        reset_metrics_collector()
        mc1 = get_metrics_collector()
        mc2 = get_metrics_collector()
        assert mc1 is mc2
        reset_metrics_collector()

    def test_latency_logging(self, caplog):
        mc = MetricsCollector()
        with caplog.at_level(logging.INFO, logger="aero.graph.metrics"):
            mc.record_graph_latency("test_node", 100.0, status="ok")
        assert any("graph_node_latency" in r.message for r in caplog.records)
