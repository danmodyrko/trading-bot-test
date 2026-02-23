from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from danbot.core.livelog import LiveEvent, LiveLogBuffer
from danbot.core.logging import sanitize_for_logging

_EVENT_FILE = Path("logs/events.jsonl")


@dataclass(slots=True)
class EventRecord:
    action: str
    message: str
    category: str = "INFO"
    severity: str = "INFO"
    symbol: str | None = None
    correlation_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class EventBus:
    def __init__(self) -> None:
        self._log = logging.getLogger(__name__)
        self._buffer = LiveLogBuffer(max_entries=4000)
        self._write_lock = Lock()

    def publish(self, record: EventRecord) -> LiveEvent:
        ts_iso = datetime.now(timezone.utc).isoformat()
        details = sanitize_for_logging(record.details)
        event = LiveEvent(
            ts_iso=ts_iso,
            severity=record.severity,
            category=record.category,
            message=record.message,
            symbol=record.symbol,
            action=record.action,
            details=details if isinstance(details, dict) else {},
        )
        self._buffer.publish(event)
        self._write_jsonl(event, record.correlation_id)
        self._write_logger(event, record.correlation_id)
        return event

    def incident(self, action: str, message: str, details: dict[str, Any] | None = None, symbol: str | None = None) -> LiveEvent:
        return self.publish(EventRecord(action=action, message=message, category="ERROR", severity="ERROR", details=details or {}, symbol=symbol))

    def drain_live_events(self, limit: int = 250) -> list[LiveEvent]:
        return self._buffer.drain(limit=limit)

    def snapshot(self) -> list[LiveEvent]:
        return self._buffer.entries

    def _write_logger(self, event: LiveEvent, correlation_id: str | None) -> None:
        payload = {"action": event.action, "symbol": event.symbol, "correlation_id": correlation_id, "payload": event.details}
        message = f"{event.message} | {json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
        level = event.severity.upper()
        if level in {"INCIDENT", "ERROR"}:
            self._log.error(message)
        elif level == "WARNING":
            self._log.warning(message)
        else:
            self._log.info(message)

    def _write_jsonl(self, event: LiveEvent, correlation_id: str | None) -> None:
        _EVENT_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": event.ts_iso,
            "level": event.severity.upper(),
            "category": event.category,
            "symbol": event.symbol,
            "action": event.action,
            "correlation_id": correlation_id,
            "payload": event.details,
        }
        with self._write_lock:
            with _EVENT_FILE.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


_EVENT_BUS = EventBus()


def get_event_bus() -> EventBus:
    return _EVENT_BUS
