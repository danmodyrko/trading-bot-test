from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

import websockets

logger = logging.getLogger(__name__)


class BinanceWsClient:
    def __init__(self, endpoint: str, stale_seconds: int = 5) -> None:
        self.endpoint = endpoint
        self.stale_seconds = stale_seconds
        self.last_message_at: datetime | None = None
        self._running = False

    @property
    def healthy(self) -> bool:
        if not self.last_message_at:
            return False
        return (datetime.now(timezone.utc) - self.last_message_at).total_seconds() < self.stale_seconds

    async def consume(self, stream: str, on_message: Callable[[dict], Awaitable[None]]) -> None:
        self._running = True
        backoff = 1
        while self._running:
            url = f"{self.endpoint}/{stream}"
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("WS connected %s", url)
                    backoff = 1
                    async for msg in ws:
                        self.last_message_at = datetime.now(timezone.utc)
                        await on_message(json.loads(msg))
            except Exception as exc:
                logger.warning("WS disconnected (%s), reconnecting in %ss", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

    def stop(self) -> None:
        self._running = False
