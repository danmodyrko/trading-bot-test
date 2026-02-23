from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from queue import Queue
from threading import Lock
from typing import Any


@dataclass(slots=True)
class LiveEvent:
    ts_iso: str
    severity: str
    category: str
    message: str
    symbol: str | None = None
    action: str = "INFO"
    details: dict[str, Any] = field(default_factory=dict)


class LiveLogBuffer:
    def __init__(self, max_entries: int = 2000) -> None:
        self._queue: Queue[LiveEvent] = Queue()
        self._entries: deque[LiveEvent] = deque(maxlen=max_entries)
        self._lock = Lock()

    def publish(self, event: LiveEvent) -> None:
        self._queue.put(event)

    def publish_now(self, message: str, severity: str = "INFO", category: str = "INFO", symbol: str | None = None, action: str = "INFO", details: dict[str, Any] | None = None) -> None:
        self.publish(
            LiveEvent(
                ts_iso=datetime.now(timezone.utc).isoformat(),
                severity=severity,
                category=category,
                message=message,
                symbol=symbol,
                action=action,
                details=details or {},
            )
        )

    def drain(self, limit: int = 200) -> list[LiveEvent]:
        out: list[LiveEvent] = []
        while len(out) < limit and not self._queue.empty():
            out.append(self._queue.get_nowait())
        if out:
            with self._lock:
                self._entries.extend(out)
        return out

    @property
    def entries(self) -> list[LiveEvent]:
        with self._lock:
            return list(self._entries)
