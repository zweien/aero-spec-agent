"""Job lifecycle events — sync and async pub/sub for job state transitions.

JobRunner publishes events, graph nodes subscribe to observe lifecycle
without frontend polling.

Event types:
  - job_started:    job entered running state
  - job_progress:   progress updated (step, percentage)
  - job_completed:  job finished successfully
  - job_failed:     job finished with error

Supports both sync (threading) and async (asyncio) subscribers.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Callable

logger = logging.getLogger(__name__)


class JobEventType(str, Enum):
    STARTED = "job_started"
    PROGRESS = "job_progress"
    COMPLETED = "job_completed"
    FAILED = "job_failed"
    WORKFLOW_STAGE = "workflow_stage"


TERMINAL_TYPES = (JobEventType.COMPLETED, JobEventType.FAILED)


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
    stage: str = ""
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    @property
    def is_terminal(self) -> bool:
        return self.type in TERMINAL_TYPES


# Type aliases
EventListener = Callable[[JobEvent], None]
AsyncEventListener = Callable[[JobEvent], Any]


class JobEventBus:
    """Thread-safe + async-compatible pub/sub for job lifecycle events.

    Supports three subscription patterns:
      1. Sync callback: bus.subscribe(callback)
      2. Async iterator: async for event in bus.astream(job_id):
      3. Async queue: queue = bus.async_queue(); await queue.get()
    """

    def __init__(self) -> None:
        self._listeners: list[EventListener] = []
        self._async_queues: list[asyncio.Queue[JobEvent]] = []
        self._lock = threading.Lock()

    # -- Sync API (backward compatible) --

    def subscribe(self, listener: EventListener) -> None:
        with self._lock:
            self._listeners.append(listener)

    def unsubscribe(self, listener: EventListener) -> None:
        with self._lock:
            self._listeners = [l for l in self._listeners if l is not listener]

    # -- Async API --

    def async_queue(self) -> asyncio.Queue[JobEvent]:
        """Create an async queue that receives all published events."""
        q: asyncio.Queue[JobEvent] = asyncio.Queue()
        with self._lock:
            self._async_queues.append(q)

        def _unsubscribe() -> None:
            with self._lock:
                try:
                    self._async_queues.remove(q)
                except ValueError:
                    pass

        # Attach cleanup callback
        q._unsubscribe = _unsubscribe  # type: ignore[attr-defined]
        return q

    def release_async_queue(self, q: asyncio.Queue[JobEvent]) -> None:
        """Remove an async queue from the bus."""
        with self._lock:
            try:
                self._async_queues.remove(q)
            except ValueError:
                pass

    async def astream(
        self,
        job_id: str | None = None,
        terminal_only: bool = False,
    ) -> AsyncIterator[JobEvent]:
        """Async iterator yielding events, optionally filtered by job_id.

        Stops after receiving a terminal event when terminal_only=True.
        """
        q = self.async_queue()
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=300)
                except asyncio.TimeoutError:
                    continue

                if job_id and event.job_id != job_id:
                    continue

                yield event

                if terminal_only and event.is_terminal:
                    return
        finally:
            self.release_async_queue(q)

    # -- Publish (called from sync JobRunner thread) --

    def publish(self, event: JobEvent) -> None:
        with self._lock:
            listeners = list(self._listeners)
            queues = list(self._async_queues)

        # Sync listeners
        for listener in listeners:
            try:
                listener(event)
            except Exception:
                logger.exception("job event listener error for %s", event.type)

        # Async queues (thread-safe put)
        for q in queues:
            try:
                q.put_nowait(event)
            except Exception:
                pass

    @property
    def listener_count(self) -> int:
        with self._lock:
            return len(self._listeners) + len(self._async_queues)


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
