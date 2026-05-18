"""Job lifecycle events — pub/sub for job state transitions.

JobRunner publishes events, graph nodes subscribe to observe lifecycle
without frontend polling.

Event types:
  - job_started:    job entered running state
  - job_progress:   progress updated (step, percentage)
  - job_completed:  job finished successfully
  - job_failed:     job finished with error
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class JobEventType(str, Enum):
    STARTED = "job_started"
    PROGRESS = "job_progress"
    COMPLETED = "job_completed"
    FAILED = "job_failed"


@dataclass
class JobEvent:
    type: JobEventType
    job_id: str
    design_id: str
    version_no: int
    timestamp: str = ""
    progress: int = 0
    current_step: str = ""
    error_message: str | None = None
    files: dict[str, str] = field(default_factory=dict)
    duration_ms: float | None = None

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


# Type alias for event callbacks
EventListener = Callable[[JobEvent], None]


class JobEventBus:
    """Thread-safe pub/sub for job lifecycle events.

    Usage:
        bus = JobEventBus()
        bus.subscribe(on_job_event)
        bus.publish(JobEvent(type=JobEventType.STARTED, ...))
    """

    def __init__(self) -> None:
        self._listeners: list[EventListener] = []
        self._lock = threading.Lock()

    def subscribe(self, listener: EventListener) -> None:
        with self._lock:
            self._listeners.append(listener)

    def unsubscribe(self, listener: EventListener) -> None:
        with self._lock:
            self._listeners = [l for l in self._listeners if l is not listener]

    def publish(self, event: JobEvent) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(event)
            except Exception:
                logger.exception("job event listener error for %s", event.type)

    @property
    def listener_count(self) -> int:
        with self._lock:
            return len(self._listeners)


# Global singleton event bus
_bus: JobEventBus | None = None


def get_job_event_bus() -> JobEventBus:
    global _bus
    if _bus is None:
        _bus = JobEventBus()
    return _bus


def reset_job_event_bus() -> None:
    """Reset the global event bus (for testing)."""
    global _bus
    _bus = None
