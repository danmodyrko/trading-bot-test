from __future__ import annotations

import asyncio
import contextlib
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DANBOT_ROOT = ROOT / "trading_bot_dan_v1"
if str(DANBOT_ROOT) not in sys.path:
    sys.path.insert(0, str(DANBOT_ROOT))

from danbot import main as danbot_main
from danbot.core.config import AppConfig, AppState, Mode, load_app_state, load_config, save_app_state
from danbot.core.events import EventRecord, get_event_bus
from danbot.core.presets import PRESETS, apply_preset, detect_profile
from danbot.exchange.adapter import ExchangeAdapter, TimeSync
from danbot.storage.db import Database
from engine.event_bus import EngineEventBus


class EngineController:
    def __init__(self, config_path: Path | str | None = None) -> None:
        self._config_path = Path(config_path or (DANBOT_ROOT / "config.toml"))
        self._config: AppConfig = load_config(self._config_path)
        self._state_path = Path(self._config.storage.app_state_path)
        self._state: AppState = load_app_state(self._state_path)
        self._events = get_event_bus()
        self._bus = EngineEventBus(history_limit=8000)
        self._running = False
        self._entries_paused = False
        self._started_at: datetime | None = None
        self._engine_task: asyncio.Task[None] | None = None
        self._event_bridge_task: asyncio.Task[None] | None = None
        self._runtime_lock = asyncio.Lock()
        self._ws_connections = 0
        self._last_latency_ms = 0
        self._time_sync = TimeSync()
        self._adapter: ExchangeAdapter | None = None
        self._db = Database(self._config.storage.sqlite_path)
        self._db.init(DANBOT_ROOT / "danbot" / "storage" / "schema.sql")
        self._ensure_runtime_components()

    @property
    def bus(self) -> EngineEventBus:
        return self._bus

    def _env_for_mode(self, mode: Mode) -> tuple[str, str]:
        if mode == Mode.DEMO:
            return os.getenv(self._config.api.demo_key_env, ""), os.getenv(self._config.api.demo_secret_env, "")
        return os.getenv(self._config.api.real_key_env, ""), os.getenv(self._config.api.real_secret_env, "")

    def _ensure_runtime_components(self) -> None:
        mode = Mode(self._config.mode)
        api_key, api_secret = self._env_for_mode(mode)
        self._adapter = ExchangeAdapter(mode=mode, api_key=api_key, api_secret=api_secret, time_sync=self._time_sync)

    async def attach(self, autostart: bool = False) -> dict[str, Any]:
        if self._event_bridge_task is None or self._event_bridge_task.done():
            self._event_bridge_task = asyncio.create_task(self._bridge_danbot_events())
        self._events.publish(EventRecord(action="API_ATTACH", message="API controller attached", category="SYSTEM"))
        if autostart:
            return await self.start()
        return {"ok": True, "message": "attached"}

    async def shutdown(self) -> None:
        await self.stop()
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
        self._state.kill_switch_engaged = True
        save_app_state(self._state_path, self._state)
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
            "paused": self._entries_paused,
            "mode": self._config.mode,
            "ws_connected": self._ws_connections > 0,
            "latency": self._last_latency_ms,
            "uptime": uptime,
        }

    async def get_account(self) -> dict[str, Any]:
        out = {"balance": "N/A", "equity": "N/A", "daily_pnl": "N/A", "reason": "not available"}
        if self._adapter:
            with contextlib.suppress(Exception):
                overview = await self._adapter.get_account_overview()
                balance = float(overview.get("balance_usdt", 0))
                unrealized = float(overview.get("unrealized_pnl", 0))
                out["balance"] = balance
                out["equity"] = balance + unrealized
                out["reason"] = ""

        since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        rows = self._db.conn.execute("SELECT pnl FROM trades WHERE ts >= ?", (since,)).fetchall()
        out["daily_pnl"] = sum(float(r["pnl"] or 0.0) for r in rows) if rows else 0.0
        return out

    async def get_positions(self) -> list[dict[str, Any]]:
        if not self._adapter:
            return []
        with contextlib.suppress(Exception):
            positions = await self._adapter.get_positions()
            return [{
                "symbol": p.get("symbol"),
                "side": "LONG" if float(p.get("positionAmt", 0)) > 0 else "SHORT",
                "qty": p.get("positionAmt"),
                "entry_price": p.get("entryPrice"),
                "mark_price": p.get("markPrice"),
                "pnl": p.get("unRealizedProfit"),
            } for p in positions]
        return []

    async def get_orders(self) -> list[dict[str, Any]]:
        if not self._adapter:
            return []
        with contextlib.suppress(Exception):
            payload = await self._adapter._signed_get("/fapi/v1/openOrders")
            if isinstance(payload, list):
                return [{
                    "id": o.get("orderId"),
                    "symbol": o.get("symbol"),
                    "type": o.get("type"),
                    "side": o.get("side"),
                    "qty": o.get("origQty"),
                    "price": o.get("price"),
                    "status": o.get("status"),
                } for o in payload]
        return []

    async def get_signals(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._db.conn.execute(
            "SELECT ts,symbol,state,confidence,side,reasons FROM signals ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    async def get_risk(self) -> dict[str, Any]:
        return {
            "kill_switch_engaged": self._state.kill_switch_engaged,
            "active_profile": detect_profile(self._state),
            "max_daily_loss_pct": self._state.max_daily_loss_pct,
            "max_positions": self._state.max_positions,
            "max_leverage": self._state.max_leverage,
        }

    async def get_settings(self) -> dict[str, Any]:
        payload = self._config.model_dump(mode="json")
        payload["app_state"] = self._state.model_dump(mode="json")
        payload["active_profile"] = detect_profile(self._state)
        return payload

    async def update_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        merged = self._config.model_dump(mode="python")
        app_state_patch = payload.pop("app_state", {}) if isinstance(payload.get("app_state", {}), dict) else {}
        for key, value in payload.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key].update(value)
            else:
                merged[key] = value
        self._config = AppConfig.model_validate(merged)
        self._write_config_toml(self._config_path, self._config.model_dump(mode="python"))
        if app_state_patch:
            state_dump = self._state.model_dump(mode="python")
            state_dump.update(app_state_patch)
            self._state = AppState.model_validate(state_dump)
            save_app_state(self._state_path, self._state)
        self._ensure_runtime_components()
        self._events.publish(EventRecord(action="SETTINGS_UPDATE", message="settings updated", category="SYSTEM", details={"keys": list(payload.keys())}))
        return await self.get_settings()

    async def apply_preset(self, name: str) -> dict[str, Any]:
        name = name.upper()
        if name not in PRESETS:
            return {"ok": False, "message": f"unknown preset {name}"}
        self._state = apply_preset(self._state, name)
        self._state.active_profile = name
        save_app_state(self._state_path, self._state)
        self._events.publish(EventRecord(action="PRESET_APPLIED", message=f"Preset applied: {name}", category="SYSTEM"))
        return {"ok": True, "preset": name, "settings": await self.get_settings()}

    async def test_connection(self, mode: str, key: str | None = None, secret: str | None = None) -> dict[str, Any]:
        target_mode = Mode(mode.upper())
        key = key if key is not None else self._env_for_mode(target_mode)[0]
        secret = secret if secret is not None else self._env_for_mode(target_mode)[1]
        adapter = ExchangeAdapter(mode=target_mode, api_key=key, api_secret=secret, time_sync=self._time_sync)
        try:
            latency = int(await adapter.ping_latency_ms())
            return {"ok": True, "mode": target_mode.value, "latency_ms": latency}
        except Exception as exc:
            return {"ok": False, "mode": target_mode.value, "reason": str(exc)}

    async def get_journal(self, page: int, limit: int) -> dict[str, Any]:
        offset = max(page - 1, 0) * limit
        rows = self._db.conn.execute(
            "SELECT id, ts, severity, category, symbol, message, json_metrics FROM lifelog ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        total = self._db.conn.execute("SELECT COUNT(1) AS total FROM lifelog").fetchone()["total"]
        return {"items": [dict(row) for row in rows], "page": page, "limit": limit, "total": total}

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
                await self._bus.publish(
                    level=event.severity,
                    category=event.category,
                    message=event.message,
                    symbol=event.symbol,
                    payload=event.details,
                )
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
