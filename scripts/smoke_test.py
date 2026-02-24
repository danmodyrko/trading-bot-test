from __future__ import annotations

import asyncio
import json
import os

import httpx
import websockets

API = os.getenv("API_URL", "http://127.0.0.1:8000")
TOKEN = os.getenv("APP_API_TOKEN", "dev-token")


async def main() -> None:
    headers = {"X-API-TOKEN": TOKEN}
    async with httpx.AsyncClient(timeout=20) as client:
        status = await client.get(f"{API}/api/status", headers=headers)
        status.raise_for_status(); print("status", status.json())
        settings = await client.get(f"{API}/api/settings", headers=headers)
        settings.raise_for_status(); print("settings keys", list(settings.json().keys())[:8])
        positions = await client.get(f"{API}/api/positions", headers=headers)
        positions.raise_for_status(); print("positions", len(positions.json()))

    ws_url = API.replace("http", "ws") + f"/ws/events?token={TOKEN}"
    async with websockets.connect(ws_url) as ws:
        first = json.loads(await ws.recv())
        print("first_ws_event", first.get("type"), list(first.keys()))


if __name__ == "__main__":
    asyncio.run(main())
