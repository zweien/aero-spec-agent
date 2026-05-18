"""Tests for GET /api/metrics endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from services.api.app.graph.metrics import get_metrics_collector, reset_metrics_collector
from services.api.app.main import app


class TestMetricsEndpoint:
    def test_returns_prometheus_text(self):
        reset_metrics_collector()
        mc = get_metrics_collector()
        mc.record_graph_request()
        mc.record_graph_latency("enqueue_job", 45.0)

        client = TestClient(app)
        resp = client.get("/api/metrics")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/plain; charset=utf-8"

        text = resp.text
        assert "graph_requests_total" in text
        assert "graph_node_latency_avg_ms" in text
        assert 'node="enqueue_job"' in text

    def test_empty_metrics_still_returns_valid_output(self):
        reset_metrics_collector()

        client = TestClient(app)
        resp = client.get("/api/metrics")
        assert resp.status_code == 200
        assert "graph_requests_total 0" in resp.text

    def test_metrics_after_deep_design(self):
        reset_metrics_collector()
        mc = get_metrics_collector()
        mc.record_deep_design(
            duration_ms=5000, status="completed", variants=3, succeeded=2,
        )

        client = TestClient(app)
        resp = client.get("/api/metrics")
        assert resp.status_code == 200
        assert "deep_design_runs_total 1" in resp.text
        assert "variant_success_rate" in resp.text

    def test_metrics_with_fallback(self):
        reset_metrics_collector()
        mc = get_metrics_collector()
        mc.record_graph_request()
        mc.record_fallback("partial")

        client = TestClient(app)
        resp = client.get("/api/metrics")
        assert "graph_fallbacks_total 1" in resp.text
        assert "graph_fallback_rate" in resp.text
