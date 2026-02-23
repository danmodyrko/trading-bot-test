from __future__ import annotations

import asyncio
import os

import httpx
import websockets

API = os.getenv("API_URL", "http://127.0.0.1:8000")
TOKEN = os.getenv("APP_API_TOKEN", "dev-token")


async def main() -> None:
    headers = {"X-API-TOKEN": TOKEN}
    async with httpx.AsyncClient(timeout=10) as client:
        status = (await client.get(f"{API}/api/status", headers=headers)).json()
        settings = (await client.get(f"{API}/api/settings", headers=headers)).json()
        print("status:", status)
        print("settings mode:", settings.get("mode"))

    ws_url = API.replace("http", "ws") + f"/ws/events?token={TOKEN}"
    async with websockets.connect(ws_url, ping_interval=None) as ws:
        for _ in range(3):
            msg = await ws.recv()
            print("ws:", msg)


if __name__ == "__main__":
    asyncio.run(main())
