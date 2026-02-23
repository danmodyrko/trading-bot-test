from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

import websockets

from danbot.core.events import EventRecord, get_event_bus
from danbot.core.logging import get_logger

logger = get_logger(__name__)


class BinanceWsClient:
    def __init__(self, endpoint: str, stale_seconds: int = 5) -> None:
        self.endpoint = endpoint
        self.stale_seconds = stale_seconds
        self.last_message_at: datetime | None = None
        self.stream_last_update: dict[str, datetime] = {}
        self._running = False
        self._events = get_event_bus()

    @property
    def healthy(self) -> bool:
        if not self.last_message_at:
            return False
        return (datetime.now(timezone.utc) - self.last_message_at).total_seconds() < self.stale_seconds

    def stale_streams(self) -> list[str]:
        now = datetime.now(timezone.utc)
        stale = [s for s, ts in self.stream_last_update.items() if (now - ts).total_seconds() > self.stale_seconds]
        if stale:
            self._events.publish(EventRecord(action="WS_STALE", message="stale streams detected", severity="WARNING", category="INCIDENT", details={"streams": stale}))
        return stale

    async def consume(self, stream: str, on_message: Callable[[dict], Awaitable[None]]) -> None:
        self._running = True
        backoff = 1
        while self._running:
            url = f"{self.endpoint}/{stream}"
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("WS connected %s", url)
                    self._events.publish(EventRecord(action="WS_RECONNECT", message="WS connected", details={"stream": stream}))
                    backoff = 1
                    async for msg in ws:
                        now = datetime.now(timezone.utc)
                        self.last_message_at = now
                        self.stream_last_update[stream] = now
                        payload = json.loads(msg)
                        evt_ts = payload.get("T") or payload.get("E")
                        if evt_ts and self.stream_last_update.get(f"{stream}:evt_ms", now) and isinstance(evt_ts, int):
                            prev_evt = payload.get("_prev_evt_ms")
                            if prev_evt and evt_ts < prev_evt:
                                logger.warning("Non-monotonic timestamp detected in %s", stream)
                            payload["_prev_evt_ms"] = evt_ts
                        await on_message(payload)
            except Exception as exc:
                logger.warning("WS disconnected (%s), reconnecting in %ss", exc, backoff)
                self._events.publish(EventRecord(action="WS_RECONNECT", message=f"WS reconnect scheduled: {exc}", severity="WARNING", category="INCIDENT", details={"stream": stream, "backoff": backoff}))
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

    def stop(self) -> None:
        self._running = False
