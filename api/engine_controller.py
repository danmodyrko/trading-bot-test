from __future__ import annotations

import asyncio
import contextlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

ROOT = Path(__file__).resolve().parents[1]
DANBOT_ROOT = ROOT / "trading_bot_dan_v1"
if str(DANBOT_ROOT) not in sys.path:
    sys.path.insert(0, str(DANBOT_ROOT))

from danbot import main as danbot_main
from danbot.core.config import AppConfig, Mode, load_config
from danbot.core.events import EventRecord, get_event_bus
from danbot.exchange import adapter as exchange_adapter
from danbot.storage.db import Database
from danbot.strategy.execution import ExecutionEngine
from engine.event_bus import EngineEventBus

EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class EngineController:
    def __init__(self, config_path: Path | str | None = None) -> None:
        self._config_path = Path(config_path or (DANBOT_ROOT / "config.toml"))
        self._config: AppConfig = load_config(self._config_path)
        self._events = get_event_bus()
        self._bus = EngineEventBus(history_limit=8000)
        self._callbacks: list[EventCallback] = []
        self._running = False
        self._entries_paused = False
        self._kill_switch_engaged = False
        self._started_at: datetime | None = None
        self._engine_task: asyncio.Task[None] | None = None
        self._event_bridge_task: asyncio.Task[None] | None = None
        self._runtime_lock = asyncio.Lock()
        self._ws_connections = 0
        self._last_latency_ms = 0
        self._adapter: exchange_adapter.ExchangeAdapter | None = None
        self._db = Database(self._config.storage.sqlite_path)
        self._db.init(DANBOT_ROOT / "danbot" / "storage" / "schema.sql")
        self._ensure_runtime_components()

    @property
    def bus(self) -> EngineEventBus:
        return self._bus

    def _ensure_runtime_components(self) -> None:
        mode = Mode(self._config.mode)
        self._adapter = exchange_adapter.ExchangeAdapter(
            mode=mode,
            api_key=os.getenv(self._config.api.demo_key_env if mode == Mode.DEMO else self._config.api.real_key_env, ""),
            api_secret=os.getenv(self._config.api.demo_secret_env if mode == Mode.DEMO else self._config.api.real_secret_env, ""),
            time_sync=exchange_adapter.TimeSync(),
        )
        self._execution_engine_loaded = ExecutionEngine is not None

    async def attach(self, autostart: bool = False) -> dict[str, Any]:
        if self._event_bridge_task is None or self._event_bridge_task.done():
            self._event_bridge_task = asyncio.create_task(self._bridge_danbot_events())
        self._events.publish(EventRecord(action="API_ATTACH", message="API controller attached", category="SYSTEM"))
        if autostart:
            return await self.start()
        return {"ok": True, "message": "attached"}

    async def shutdown(self) -> None:
        if self._engine_task and not self._engine_task.done():
            self._engine_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._engine_task
        if self._event_bridge_task and not self._event_bridge_task.done():
            self._event_bridge_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._event_bridge_task

    async def start(self) -> dict[str, Any]:
        async with self._runtime_lock:
            if self._running:
                return {"ok": True, "message": "already running"}
            self._running = True
            self._entries_paused = False
            self._kill_switch_engaged = False
            self._started_at = datetime.now(timezone.utc)
            if self._engine_task is None or self._engine_task.done():
                self._engine_task = asyncio.create_task(danbot_main.run_headless())
            self._events.publish(EventRecord(action="ENGINE_START", message="engine started", category="SYSTEM"))
        return {"ok": True, "message": "started"}

    async def stop(self) -> dict[str, Any]:
        async with self._runtime_lock:
            self._running = False
            self._entries_paused = False
            if self._engine_task and not self._engine_task.done():
                self._engine_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._engine_task
            self._events.publish(EventRecord(action="ENGINE_STOP", message="engine stopped", category="SYSTEM", severity="WARNING"))
        return {"ok": True, "message": "stopped"}

    async def pause_entries(self) -> dict[str, Any]:
        self._entries_paused = True
        self._events.publish(EventRecord(action="PAUSE_ENTRIES", message="entries paused", category="RISK", severity="WARNING"))
        return {"ok": True}

    async def resume_entries(self) -> dict[str, Any]:
        self._entries_paused = False
        self._events.publish(EventRecord(action="RESUME_ENTRIES", message="entries resumed", category="RISK"))
        return {"ok": True}

    async def flatten(self) -> dict[str, Any]:
        self._events.publish(EventRecord(action="FLATTEN", message="flatten requested", category="POSITION", severity="WARNING"))
        return {"ok": True}

    async def kill_switch(self) -> dict[str, Any]:
        self._kill_switch_engaged = True
        await self.stop()
        self._entries_paused = True
        self._events.publish(EventRecord(action="KILL_SWITCH", message="kill switch engaged", category="RISK", severity="ERROR"))
        return {"ok": True}

    async def get_status(self) -> dict[str, Any]:
        uptime = 0
        if self._running and self._started_at:
            uptime = int((datetime.now(timezone.utc) - self._started_at).total_seconds())
        return {
            "running": self._running,
            "entries_paused": self._entries_paused,
            "kill_switch_engaged": self._kill_switch_engaged,
            "mode": self._config.mode.value,
            "uptime_seconds": uptime,
            "ws_connected": self._ws_connections > 0,
            "latency_ms": self._last_latency_ms,
        }

    async def get_account_state(self) -> dict[str, Any]:
        if not self._adapter:
            return {}
        try:
            account = await self._adapter.get_account_overview()
            return {"balance": account["balance_usdt"], "equity": account["balance_usdt"] + account["unrealized_pnl"], **account}
        except Exception as exc:
            return {"error": str(exc), "balance": 0.0, "equity": 0.0}

    async def get_positions(self) -> list[dict[str, Any]]:
        if not self._adapter:
            return []
        with contextlib.suppress(Exception):
            return await self._adapter.get_positions()
        return []

    async def get_orders(self) -> list[dict[str, Any]]:
        if not self._adapter:
            return []
        with contextlib.suppress(Exception):
            orders = await self._adapter._signed_get("/fapi/v1/openOrders")
            if isinstance(orders, list):
                return orders
        return []

    async def get_settings(self) -> dict[str, Any]:
        return self._config.model_dump(mode="json")

    async def update_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        merged = self._config.model_dump(mode="python")
        for key, value in payload.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key].update(value)
            else:
                merged[key] = value
        self._config = AppConfig.model_validate(merged)
        self._write_config_toml(self._config_path, self._config.model_dump(mode="python"))
        self._ensure_runtime_components()
        self._events.publish(EventRecord(action="SETTINGS_UPDATE", message="settings updated", category="SYSTEM", details=payload))
        return self._config.model_dump(mode="json")

    async def test_connection(self, mode: str) -> dict[str, Any]:
        target_mode = Mode(mode.upper())
        if self._adapter:
            self._adapter.switch_mode(target_mode)
            with contextlib.suppress(Exception):
                latency = int(await self._adapter.ping_latency_ms())
                return {"ok": True, "mode": target_mode.value, "latency_ms": latency}
        return {"ok": False, "mode": target_mode.value, "message": "adapter unavailable"}

    async def get_journal(self, page: int, page_size: int) -> dict[str, Any]:
        offset = max(page - 1, 0) * page_size
        rows = self._db.conn.execute(
            "SELECT id, ts, severity, category, symbol, message, json_metrics FROM lifelog ORDER BY id DESC LIMIT ? OFFSET ?",
            (page_size, offset),
        ).fetchall()
        total = self._db.conn.execute("SELECT COUNT(1) AS total FROM lifelog").fetchone()["total"]
        return {"items": [dict(row) for row in rows], "page": page, "page_size": page_size, "total": total}

    def subscribe_events(self, callback: EventCallback) -> None:
        self._callbacks.append(callback)

    def register_ws(self) -> None:
        self._ws_connections += 1

    def unregister_ws(self) -> None:
        self._ws_connections = max(0, self._ws_connections - 1)

    async def ping_latency(self) -> None:
        if not self._adapter:
            self._last_latency_ms = 0
            return
        with contextlib.suppress(Exception):
            self._last_latency_ms = int(await self._adapter.ping_latency_ms())
            return
        self._last_latency_ms = 0

    async def _bridge_danbot_events(self) -> None:
        while True:
            for event in self._events.drain_live_events(limit=250):
                packet = {"ts": event.ts_iso, "category": event.category, "level": event.severity, "message": event.message, "payload": event.details}
                await self._bus.publish(level=packet["level"], category=packet["category"], message=packet["message"], symbol=event.symbol, payload=packet["payload"])
                for callback in list(self._callbacks):
                    result = callback(packet)
                    if asyncio.iscoroutine(result):
                        await result
            await asyncio.sleep(0.25)

    def _write_config_toml(self, path: Path, config_data: dict[str, Any]) -> None:
        lines: list[str] = []
        root_keys = ["mode", "exchange", "symbols", "auto_discover_symbols", "min_quote_volume_24h", "min_trade_rate_baseline", "max_symbols_active"]
        for key in root_keys:
            if key in config_data:
                lines.append(f"{key} = {self._toml_value(config_data[key])}")
        for section in ["endpoints", "risk", "strategy", "execution", "ui", "storage", "api"]:
            values = config_data.get(section)
            if isinstance(values, dict):
                lines.extend(["", f"[{section}]"])
                for key, value in values.items():
                    lines.append(f"{key} = {self._toml_value(value)}")
        path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    def _toml_value(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            return f'"{value}"'
        if isinstance(value, Path):
            return f'"{value.as_posix()}"'
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, (list, tuple)):
            return "[" + ", ".join(self._toml_value(v) for v in value) + "]"
        return f'"{value}"'
