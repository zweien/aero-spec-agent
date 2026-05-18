"""Graph runtime metrics — structured logging and Prometheus-compatible counters.

Metrics collected:
  - fallback_rate: ratio of legacy fallbacks vs graph-mode requests
  - graph_latency: node execution latency histograms
  - deep_design_runtime: end-to-end deep design graph duration
  - variant_success_rate: ratio of succeeded vs total variants

Usage:
    from services.api.app.graph.metrics import get_metrics_collector

    mc = get_metrics_collector()
    mc.record_graph_latency("enqueue_job", 45.2, status="ok")
    mc.record_fallback("partial")
    mc.record_deep_design(duration_ms=12345, status="completed", variants=3, succeeded=2)
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("aero.graph.metrics")


@dataclass
class MetricSnapshot:
    """Point-in-time snapshot of all collected metrics."""

    total_requests: int = 0
    graph_requests: int = 0
    fallback_requests: int = 0
    deep_design_runs: int = 0
    total_variants: int = 0
    succeeded_variants: int = 0
    node_latencies: dict[str, list[float]] = field(default_factory=dict)

    @property
    def fallback_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.fallback_requests / self.total_requests

    @property
    def variant_success_rate(self) -> float:
        if self.total_variants == 0:
            return 0.0
        return self.succeeded_variants / self.total_variants

    def to_prometheus(self) -> str:
        """Export metrics in Prometheus exposition format."""
        lines = [
            "# HELP graph_requests_total Total graph mode requests",
            "# TYPE graph_requests_total counter",
            f"graph_requests_total {self.graph_requests}",
            "",
            "# HELP graph_fallbacks_total Total fallbacks to legacy mode",
            "# TYPE graph_fallbacks_total counter",
            f"graph_fallbacks_total {self.fallback_requests}",
            "",
            "# HELP graph_fallback_rate Ratio of legacy fallbacks",
            "# TYPE graph_fallback_rate gauge",
            f"graph_fallback_rate {self.fallback_rate:.4f}",
            "",
            "# HELP deep_design_runs_total Total deep design graph runs",
            "# TYPE deep_design_runs_total counter",
            f"deep_design_runs_total {self.deep_design_runs}",
            "",
            "# HELP variant_success_rate Ratio of succeeded variants",
            "# TYPE variant_success_rate gauge",
            f"variant_success_rate {self.variant_success_rate:.4f}",
            "",
            "# HELP variants_total Total variants explored",
            "# TYPE variants_total counter",
            f"variants_total {self.total_variants}",
            "",
            "# HELP variants_succeeded_total Total succeeded variants",
            "# TYPE variants_succeeded_total counter",
            f"variants_succeeded_total {self.succeeded_variants}",
        ]

        for node, latencies in self.node_latencies.items():
            if latencies:
                avg = sum(latencies) / len(latencies)
                lines.extend([
                    f"# HELP graph_node_latency_avg_ms Average latency for {node}",
                    f"# TYPE graph_node_latency_avg_ms gauge",
                    f'graph_node_latency_avg_ms{{node="{node}"}} {avg:.2f}',
                    "",
                ])

        return "\n".join(lines)


class MetricsCollector:
    """Thread-safe collector for graph runtime metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot = MetricSnapshot()

    def record_graph_request(self) -> None:
        with self._lock:
            self._snapshot.total_requests += 1
            self._snapshot.graph_requests += 1
        logger.info("graph_request", extra={"metric": "graph_request"})

    def record_fallback(self, mode: str) -> None:
        with self._lock:
            self._snapshot.total_requests += 1
            self._snapshot.fallback_requests += 1
        logger.info("graph_fallback", extra={"metric": "fallback", "mode": mode})

    def record_graph_latency(self, node: str, latency_ms: float, *, status: str = "ok") -> None:
        with self._lock:
            latencies = self._snapshot.node_latencies.setdefault(node, [])
            latencies.append(latency_ms)
        logger.info(
            "graph_node_latency",
            extra={"metric": "latency", "node": node, "latency_ms": round(latency_ms, 2), "status": status},
        )

    def record_deep_design(
        self,
        *,
        duration_ms: float,
        status: str,
        variants: int,
        succeeded: int,
    ) -> None:
        with self._lock:
            self._snapshot.deep_design_runs += 1
            self._snapshot.total_variants += variants
            self._snapshot.succeeded_variants += succeeded
        logger.info(
            "deep_design_completed",
            extra={
                "metric": "deep_design",
                "duration_ms": round(duration_ms, 2),
                "status": status,
                "variants": variants,
                "succeeded": succeeded,
            },
        )

    def snapshot(self) -> MetricSnapshot:
        with self._lock:
            return MetricSnapshot(
                total_requests=self._snapshot.total_requests,
                graph_requests=self._snapshot.graph_requests,
                fallback_requests=self._snapshot.fallback_requests,
                deep_design_runs=self._snapshot.deep_design_runs,
                total_variants=self._snapshot.total_variants,
                succeeded_variants=self._snapshot.succeeded_variants,
                node_latencies={k: list(v) for k, v in self._snapshot.node_latencies.items()},
            )


_collector: MetricsCollector | None = None
_collector_lock = threading.Lock()


def get_metrics_collector() -> MetricsCollector:
    global _collector
    with _collector_lock:
        if _collector is None:
            _collector = MetricsCollector()
        return _collector


def reset_metrics_collector() -> None:
    global _collector
    with _collector_lock:
        _collector = None
