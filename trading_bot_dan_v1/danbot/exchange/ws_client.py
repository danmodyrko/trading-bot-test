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
            self._events.publish(EventRecord(action="WS_STALE", message="stale streams detected", severity="WARNING", category="WS", details={"streams": stale}))
        return stale

    async def consume(self, stream: str, on_message: Callable[[dict], Awaitable[None]]) -> None:
        self._running = True
        backoff = 1.0
        while self._running:
            url = f"{self.endpoint}/{stream}"
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("WS connected %s", url)
                    self._events.publish(EventRecord(action="WS_RECONNECT", message="ws connected", category="WS", details={"stream": stream}))
                    backoff = 1.0
                    async for msg in ws:
                        now = datetime.now(timezone.utc)
                        self.last_message_at = now
                        self.stream_last_update[stream] = now
                        await on_message(json.loads(msg))
            except Exception as exc:  # pragma: no cover
                logger.warning("WS disconnected (%s), reconnecting in %.1fs", exc, backoff)
                self._events.publish(
                    EventRecord(action="WS_RECONNECT", message=f"ws reconnect scheduled: {exc}", severity="WARNING", category="WS", details={"stream": stream, "backoff": backoff})
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)

    def stop(self) -> None:
        self._running = False


class WebsocketSupervisor:
    def __init__(self, client: BinanceWsClient, stale_after_s: int = 10, check_interval_s: float = 2.0) -> None:
        self.client = client
        self.stale_after_s = stale_after_s
        self.check_interval_s = check_interval_s
        self._events = get_event_bus()
        self._tasks: list[asyncio.Task] = []
        self._running = False

    async def start(self, streams: list[str], on_message: Callable[[dict], Awaitable[None]]) -> None:
        self._running = True
        for stream in streams:
            self._tasks.append(asyncio.create_task(self.client.consume(stream, on_message)))
        self._tasks.append(asyncio.create_task(self._monitor_staleness(streams, on_message)))

    async def _monitor_staleness(self, streams: list[str], on_message: Callable[[dict], Awaitable[None]]) -> None:
        while self._running:
            await asyncio.sleep(self.check_interval_s)
            stale = self.client.stale_streams()
            if not stale:
                continue
            for stream in stale:
                self._events.publish(EventRecord(action="WS_RESTART", message="restarting stale stream", category="WS", severity="WARNING", details={"stream": stream}))
                self._tasks.append(asyncio.create_task(self.client.consume(stream, on_message)))

    async def stop(self) -> None:
        self._running = False
        self.client.stop()
        for task in self._tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
