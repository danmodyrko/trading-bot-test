from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import Depends, FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.engine_controller import EngineController
from api.security import require_rest_token, require_ws_token


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        if not self.directory or not Path(self.directory).exists():
            return PlainTextResponse("Frontend build is not available. Build web/dist first.", status_code=503)
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and scope["method"] == "GET":
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404 and scope["method"] == "GET":
            return await super().get_response("index.html", scope)
        return response


controller = EngineController()
UI_DIST_DIR = Path(__file__).resolve().parents[1] / "web" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    await controller.attach(autostart=os.getenv("APP_AUTOSTART", "false").lower() in {"1", "true", "yes"})
    yield
    await controller.shutdown()


app = FastAPI(title="Trader Bot Control Center API", version="2.0", lifespan=lifespan)

if os.getenv("APP_ENV", "prod").lower() == "dev":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.post("/api/start", dependencies=[Depends(require_rest_token)])
async def start(): return await controller.start()


@app.post("/api/stop", dependencies=[Depends(require_rest_token)])
async def stop(): return await controller.stop()


@app.post("/api/pause", dependencies=[Depends(require_rest_token)])
async def pause(): return await controller.pause_entries()


@app.post("/api/resume", dependencies=[Depends(require_rest_token)])
async def resume(): return await controller.resume_entries()


@app.post("/api/flatten", dependencies=[Depends(require_rest_token)])
async def flatten(): return await controller.flatten()


@app.post("/api/kill", dependencies=[Depends(require_rest_token)])
async def kill(): return await controller.kill_switch()


@app.post("/api/test-connection", dependencies=[Depends(require_rest_token)])
async def test_connection(payload: dict):
    return await controller.test_connection(payload.get("mode", "DEMO"), payload.get("key"), payload.get("secret"))


@app.post("/api/preset/{name}", dependencies=[Depends(require_rest_token)])
async def preset(name: str):
    return await controller.apply_preset(name)


@app.get("/api/status", dependencies=[Depends(require_rest_token)])
async def status():
    await controller.ping_latency()
    return await controller.get_status()


@app.get("/api/account", dependencies=[Depends(require_rest_token)])
async def account(): return await controller.get_account()


@app.get("/api/positions", dependencies=[Depends(require_rest_token)])
async def positions(): return await controller.get_positions()


@app.get("/api/orders", dependencies=[Depends(require_rest_token)])
async def orders(): return await controller.get_orders()


@app.get("/api/signals", dependencies=[Depends(require_rest_token)])
async def signals(limit: int = Query(default=100, ge=1, le=500)): return await controller.get_signals(limit)


@app.get("/api/risk", dependencies=[Depends(require_rest_token)])
async def risk(): return await controller.get_risk()


@app.get("/api/settings", dependencies=[Depends(require_rest_token)])
async def settings(): return await controller.get_settings()


@app.put("/api/settings", dependencies=[Depends(require_rest_token)])
async def update_settings(payload: dict): return await controller.update_settings(payload)


@app.get("/api/journal", dependencies=[Depends(require_rest_token)])
async def journal(page: int = Query(default=1, ge=1), limit: int = Query(default=50, ge=1, le=500)):
    return await controller.get_journal(page=page, limit=limit)


@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    await websocket.accept()
    try:
        await require_ws_token(websocket)
    except RuntimeError:
        return
    queue = await controller.bus.subscribe(maxsize=512)
    controller.register_ws()
    try:
        await websocket.send_json({
            "type": "INITIAL_SNAPSHOT",
            "status": await controller.get_status(),
            "account": await controller.get_account(),
            "positions": await controller.get_positions(),
            "orders": await controller.get_orders(),
            "signals": await controller.get_signals(100),
            "risk": await controller.get_risk(),
            "settings": await controller.get_settings(),
            "events": controller.bus.snapshot(limit=200),
        })

        async def producer() -> None:
            while True:
                event = await queue.get()
                try:
                    await websocket.send_json({"type": "EVENT", "event": event})
                except (WebSocketDisconnect, RuntimeError):
                    break

        async def ticker() -> None:
            while True:
                await asyncio.sleep(1)
                await controller.ping_latency()
                try:
                    await websocket.send_json({"type": "STATUS_TICK", "status": await controller.get_status(), "account": await controller.get_account()})
                except (WebSocketDisconnect, RuntimeError):
                    break

        async def consumer() -> None:
            while True:
                try:
                    await websocket.receive_text()
                except WebSocketDisconnect:
                    break

        tasks = [asyncio.create_task(producer()), asyncio.create_task(ticker()), asyncio.create_task(consumer())]
        await asyncio.gather(*tasks, return_exceptions=True)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        await controller.bus.unsubscribe(queue)
        controller.unregister_ws()
        for task in [t for t in locals().get("tasks", []) if isinstance(t, asyncio.Task)]:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


app.mount("/", SPAStaticFiles(directory=UI_DIST_DIR, html=True, check_dir=False), name="web")
