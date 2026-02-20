from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator


async def replay_stream(items: list[dict], speed: float = 1.0) -> AsyncIterator[dict]:
    for item in items:
        await asyncio.sleep(max(0.0, 1.0 / speed))
        yield item
