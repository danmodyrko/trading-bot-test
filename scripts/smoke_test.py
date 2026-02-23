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
    async with httpx.AsyncClient(timeout=30) as client:
        start = await client.post(f"{API}/api/start", headers=headers)
        start.raise_for_status()
        print("start:", start.json())

        ws_url = API.replace("http", "ws") + f"/ws/events?token={TOKEN}"
        async with websockets.connect(ws_url, ping_interval=None) as ws:
            await ws.recv()  # snapshot
            event = None
            for _ in range(20):
                payload = json.loads(await ws.recv())
                if payload.get("type") == "event":
                    event = payload["event"]
                    break
            if not event:
                raise RuntimeError("No websocket event received")
            print("event:", event)

        positions = await client.get(f"{API}/api/positions", headers=headers)
        positions.raise_for_status()
        print("positions:", positions.json())

        stop = await client.post(f"{API}/api/stop", headers=headers)
        stop.raise_for_status()
        print("stop:", stop.json())


if __name__ == "__main__":
    asyncio.run(main())
