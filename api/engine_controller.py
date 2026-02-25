from __future__ import annotations

import asyncio
import contextlib
import json
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
        self._credentials_path = DANBOT_ROOT / "data" / "api_credentials.json"
        self._credentials = self._load_credentials()
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
        self._last_test_order: dict[str, Any] | None = None
        self._ensure_runtime_components()

    @property
    def bus(self) -> EngineEventBus:
        return self._bus

    def _load_credentials(self) -> dict[str, dict[str, str]]:
        if not self._credentials_path.exists():
            return {"DEMO": {"key": "", "secret": ""}, "REAL": {"key": "", "secret": ""}}
        try:
            payload = json.loads(self._credentials_path.read_text(encoding="utf-8"))
            return {
                "DEMO": {"key": payload.get("DEMO", {}).get("key", ""), "secret": payload.get("DEMO", {}).get("secret", "")},
                "REAL": {"key": payload.get("REAL", {}).get("key", ""), "secret": payload.get("REAL", {}).get("secret", "")},
            }
        except Exception:
            return {"DEMO": {"key": "", "secret": ""}, "REAL": {"key": "", "secret": ""}}

    def _save_credentials(self) -> None:
        self._credentials_path.parent.mkdir(parents=True, exist_ok=True)
        self._credentials_path.write_text(json.dumps(self._credentials, indent=2), encoding="utf-8")

    def _env_for_mode(self, mode: Mode) -> tuple[str, str]:
        profile = self._credentials.get(mode.value, {})
        key, secret = profile.get("key", ""), profile.get("secret", "")
        if key and secret:
            return key, secret
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
            "ws_clients": self._ws_connections,
            "latency_ms": self._last_latency_ms,
            "uptime_seconds": uptime,
            "connected_exchange": self._config.exchange,
            "server_time": datetime.now(timezone.utc).isoformat(),
            "reconnecting": self._last_latency_ms <= 0,
        }

    async def get_account(self) -> dict[str, Any]:
        if not self._adapter:
            return {"balance": "—", "equity": "—", "daily_pnl": "—", "open_positions": 0, "active_orders": 0}
        try:
            overview = await self._adapter.get_account_overview()
            bal = float(overview.get("balance_usdt", 0.0))
            eq = bal + float(overview.get("unrealized_pnl", 0.0))
            return {
                "balance": f"{bal:.2f}",
                "equity": f"{eq:.2f}",
                "daily_pnl": f"{float(overview.get('unrealized_pnl', 0.0)):.2f}",
                "open_positions": len(await self.get_positions()),
                "active_orders": len(await self.get_orders()),
            }
        except Exception as exc:
            return {
                "balance": "—",
                "equity": "—",
                "daily_pnl": "—",
                "open_positions": 0,
                "active_orders": 0,
                "reason": str(exc),
            }

    async def get_positions(self) -> list[dict[str, Any]]:
        if not self._adapter:
            return []
        try:
            payload = await self._adapter.get_positions()
            return [
                {
                    "symbol": p.get("symbol"),
                    "side": "LONG" if float(p.get("positionAmt", 0)) > 0 else "SHORT",
                    "qty": p.get("positionAmt"),
                    "entry_price": p.get("entryPrice"),
                    "mark_price": p.get("markPrice"),
                    "pnl": p.get("unRealizedProfit"),
                }
                for p in payload
            ]
        except Exception:
            return []

    async def get_orders(self) -> list[dict[str, Any]]:
        if not self._adapter:
            return []
        try:
            payload = await self._adapter.client.get("/fapi/v1/openOrders", signed=True)
            if isinstance(payload, list):
                return [{"id": o.get("orderId"), "symbol": o.get("symbol"), "type": o.get("type"), "side": o.get("side"), "qty": o.get("origQty"), "price": o.get("price"), "status": o.get("status")} for o in payload]
        except Exception:
            return []
        return []

    async def get_signals(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._db.conn.execute("SELECT ts,symbol,state,confidence,side,reasons FROM signals ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
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
        payload["credentials"] = {
            "DEMO": {"key": self._credentials.get("DEMO", {}).get("key", ""), "secret": self._credentials.get("DEMO", {}).get("secret", "")},
            "REAL": {"key": self._credentials.get("REAL", {}).get("key", ""), "secret": self._credentials.get("REAL", {}).get("secret", "")},
        }
        return payload

    async def update_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        credentials = payload.pop("credentials", None)
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
        if isinstance(credentials, dict):
            for mode in ["DEMO", "REAL"]:
                item = credentials.get(mode, {})
                if isinstance(item, dict):
                    self._credentials[mode] = {
                        "key": str(item.get("key", self._credentials.get(mode, {}).get("key", ""))),
                        "secret": str(item.get("secret", self._credentials.get(mode, {}).get("secret", ""))),
                    }
            self._save_credentials()
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
        checks: dict[str, Any] = {"mode": target_mode.value, "api_key_present": bool(key), "api_secret_present": bool(secret)}
        try:
            checks["ping_latency_ms"] = int(await adapter.ping_latency_ms())
            time_payload = await adapter.client.get("/fapi/v1/time")
            checks["server_time"] = time_payload.get("serverTime")
            if key and secret:
                account = await adapter.get_account_overview()
                checks["account"] = {
                    "balance_usdt": account.get("balance_usdt", 0),
                    "available_usdt": account.get("available_usdt", 0),
                }
            return {"ok": True, "checks": checks}
        except Exception as exc:
            return {"ok": False, "checks": checks, "reason": str(exc)}

    async def place_test_trade(self, symbol: str, quote_value_usdt: float = 100.0, side: str = "BUY") -> dict[str, Any]:
        if Mode(self._config.mode) != Mode.DEMO:
            return {"ok": False, "reason": "Test trade is allowed only in DEMO mode."}
        if not self._adapter:
            return {"ok": False, "reason": "Adapter is not initialized."}
        result = await self._adapter.place_test_trade(symbol=symbol, quote_value_usdt=quote_value_usdt, side=side)
        self._last_test_order = result.get("order")
        await self._bus.publish(level="INFO", category="ORDER", message="Test trade placed", symbol=symbol, payload=result)
        return result

    async def cancel_test_trade(self, symbol: str | None = None) -> dict[str, Any]:
        if not self._adapter:
            return {"ok": False, "reason": "Adapter is not initialized."}
        if not self._last_test_order:
            return {"ok": False, "reason": "No test order tracked in current session."}
        order = self._last_test_order
        params = {"symbol": symbol or order.get("symbol"), "orderId": order.get("orderId")}
        try:
            payload = await self._adapter.client.delete("/fapi/v1/order", params=params, signed=True)
            await self._bus.publish(level="WARNING", category="ORDER", message="Test trade cancel requested", symbol=params["symbol"], payload=payload)
            return {"ok": True, "cancel": payload}
        except Exception as exc:
            return {"ok": False, "reason": str(exc), "params": params}

    async def clear_system_logs(self) -> dict[str, Any]:
        self._db.conn.execute("DELETE FROM lifelog")
        self._db.conn.commit()
        self._bus.clear_history()
        await self._bus.publish(level="WARNING", category="SYSTEM", message="System logs cleared from UI")
        return {"ok": True}

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
        last_ws_event_at = datetime.now(timezone.utc)
        while True:
            drained = self._events.drain_live_events(limit=250)
            for event in drained:
                await self._bus.publish(
                    level=event.severity,
                    category=event.category,
                    message=event.message,
                    symbol=event.symbol,
                    payload=event.details,
                )
                last_ws_event_at = datetime.now(timezone.utc)
            if datetime.now(timezone.utc) - last_ws_event_at > timedelta(seconds=8):
                await self._bus.publish(level="WARNING", category="WS", message="Market stream stale (>8s), reconnect monitor active")
                last_ws_event_at = datetime.now(timezone.utc)
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
