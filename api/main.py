from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import Depends, FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from api.security import require_rest_token, require_ws_token
from engine import EngineController


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        if not self.directory or not Path(self.directory).exists():
            return PlainTextResponse(
                "Frontend build is not available. Install Node.js LTS and run the frontend build.",
                status_code=503,
            )

        response = await super().get_response(path, scope)
        if response.status_code == 404 and scope["method"] == "GET":
            return await super().get_response("index.html", scope)
        return response


def _is_dev_mode() -> bool:
    return os.getenv("APP_ENV", "prod").lower() == "dev"


def _is_autostart_enabled() -> bool:
    value = os.getenv("APP_AUTOSTART", "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _build_frontend_if_missing(ui_dist_dir: Path) -> None:
    if ui_dist_dir.exists():
        return

    npm_cmd = shutil.which("npm")
    if not npm_cmd:
        print(
            "Node.js/npm not installed.\n"
            "Backend started without UI.\n"
            "Install Node.js LTS to enable dashboard."
        )
        return

    web_dir = ui_dist_dir.parent
    print("web/dist missing: attempting automatic frontend build...")
    try:
        subprocess.run([npm_cmd, "install"], cwd=web_dir, check=True)
        subprocess.run([npm_cmd, "run", "build"], cwd=web_dir, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"Frontend build failed: {exc}")
        print("Backend started without UI.")


controller = EngineController()
UI_DIST_DIR = Path(__file__).resolve().parents[1] / "web" / "dist"
_build_frontend_if_missing(UI_DIST_DIR)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await controller.attach(autostart=_is_autostart_enabled())
    yield
    await controller.shutdown()


app = FastAPI(title="Trader Bot Control Center API", version="2.0", lifespan=lifespan)

if _is_dev_mode():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.post("/api/start", dependencies=[Depends(require_rest_token)])
async def start():
    return await controller.start()


@app.post("/api/stop", dependencies=[Depends(require_rest_token)])
async def stop():
    return await controller.stop()


@app.post("/api/pause", dependencies=[Depends(require_rest_token)])
async def pause():
    return await controller.pause_entries()


@app.post("/api/resume", dependencies=[Depends(require_rest_token)])
async def resume():
    return await controller.resume_entries()


@app.post("/api/flatten", dependencies=[Depends(require_rest_token)])
async def flatten():
    return await controller.flatten()


@app.post("/api/kill", dependencies=[Depends(require_rest_token)])
async def kill():
    return await controller.kill_switch()


@app.get("/api/status", dependencies=[Depends(require_rest_token)])
async def status():
    return await controller.get_status()


@app.get("/api/settings", dependencies=[Depends(require_rest_token)])
async def settings():
    return await controller.get_settings()


@app.put("/api/settings", dependencies=[Depends(require_rest_token)])
async def update_settings(payload: dict):
    return await controller.update_settings(payload)


@app.post("/api/test-connection", dependencies=[Depends(require_rest_token)])
async def test_connection(payload: dict):
    mode = payload.get("mode", "DEMO")
    return await controller.test_connection(mode)


@app.get("/api/positions", dependencies=[Depends(require_rest_token)])
async def positions():
    return await controller.get_positions()


@app.get("/api/orders", dependencies=[Depends(require_rest_token)])
async def orders():
    return await controller.get_open_orders()


@app.get("/api/signals", dependencies=[Depends(require_rest_token)])
async def signals():
    return await controller.get_recent_signals()


@app.get("/api/journal", dependencies=[Depends(require_rest_token)])
async def journal(page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=500)):
    return await controller.get_journal(page=page, page_size=page_size)


@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    await websocket.accept()
    try:
        await require_ws_token(websocket)
    except RuntimeError:
        return

    queue = await controller.bus.subscribe(maxsize=256)

    initial = {
        "type": "snapshot",
        "status": await controller.get_status(),
        "settings": await controller.get_settings(),
        "positions": await controller.get_positions(),
        "orders": await controller.get_open_orders(),
        "events": controller.bus.snapshot(limit=80),
    }
    await websocket.send_json(initial)

    async def producer() -> None:
        while True:
            event = await queue.get()
            await websocket.send_json({"type": "event", "event": event})

    async def ticker() -> None:
        while True:
            await asyncio.sleep(1.0)
            await websocket.send_json({"type": "status", "status": await controller.get_status()})

    async def heartbeat() -> None:
        while True:
            await asyncio.sleep(10)
            await websocket.send_json({"type": "ping"})

    async def consumer() -> None:
        while True:
            payload = await websocket.receive_json()
            if payload.get("type") == "pong":
                continue

    tasks = [
        asyncio.create_task(producer()),
        asyncio.create_task(ticker()),
        asyncio.create_task(heartbeat()),
        asyncio.create_task(consumer()),
    ]
    try:
        await asyncio.gather(*tasks)
    except WebSocketDisconnect:
        pass
    finally:
        for task in tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        await controller.bus.unsubscribe(queue)


app.mount("/", SPAStaticFiles(directory=UI_DIST_DIR, html=True, check_dir=False), name="web")
