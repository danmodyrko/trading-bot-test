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
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{API}/api/status", headers=headers)
        response.raise_for_status()
        print("/api/status:", response.json())

    ws_url = API.replace("http", "ws") + f"/ws/events?token={TOKEN}"
    async with websockets.connect(ws_url, ping_interval=None) as ws:
        first_message = await ws.recv()
        try:
            first_message = json.loads(first_message)
        except json.JSONDecodeError:
            pass
        print("first websocket event:", first_message)


if __name__ == "__main__":
    asyncio.run(main())
