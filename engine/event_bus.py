from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any


class EngineEventBus:
    def __init__(self, history_limit: int = 5000) -> None:
        self._history: deque[dict[str, Any]] = deque(maxlen=history_limit)
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._lock = asyncio.Lock()

    async def publish(
        self,
        *,
        level: str,
        category: str,
        message: str,
        symbol: str | None = None,
        correlation_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level.upper(),
            "category": category.upper(),
            "message": message,
            "symbol": symbol,
            "correlation_id": correlation_id,
            "payload": payload or {},
        }
        async with self._lock:
            self._history.append(event)
            for queue in list(self._subscribers):
                if queue.full():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    continue
        return event

    async def subscribe(self, maxsize: int = 256) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=maxsize)
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    def snapshot(self, limit: int = 200) -> list[dict[str, Any]]:
        return list(self._history)[-limit:]

    def clear_history(self) -> None:
        self._history.clear()
