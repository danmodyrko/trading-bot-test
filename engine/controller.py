from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel

from engine.event_bus import EngineEventBus
from trading_bot_dan_v1.danbot.core.config import AppState, Mode, load_app_state, save_app_state


class EngineStatus(BaseModel):
    running: bool = False
    entries_paused: bool = False
    kill_switch_engaged: bool = False
    mode: Literal["DEMO", "REAL"] = "DEMO"
    started_at: str | None = None
    uptime_seconds: int = 0
    ws_latency_ms: int = 0
    balance: float = 1000.0
    equity: float = 1000.0
    daily_pnl: float = 0.0


class EngineController:
    def __init__(self, app_state_path: str = "data/app_state.json") -> None:
        self._lock = asyncio.Lock()
        self._app_state_path = app_state_path
        self._app_state = load_app_state(path=self._state_path)
        self._status = EngineStatus(mode=self._app_state.mode.value, kill_switch_engaged=self._app_state.kill_switch_engaged)
        self._positions: list[dict[str, Any]] = []
        self._orders: list[dict[str, Any]] = []
        self._signals: list[dict[str, Any]] = []
        self._journal: list[dict[str, Any]] = []
        self._bus = EngineEventBus(history_limit=8000)
        self._task: asyncio.Task[None] | None = None
        self._last_tick = datetime.now(timezone.utc)

    @property
    def _state_path(self):
        from pathlib import Path

        return Path(self._app_state_path)

    @property
    def bus(self) -> EngineEventBus:
        return self._bus

    async def start(self) -> dict[str, Any]:
        async with self._lock:
            if self._status.running:
                return {"ok": True, "message": "already running"}
            self._status.running = True
            self._status.started_at = datetime.now(timezone.utc).isoformat()
            self._status.kill_switch_engaged = False
            self._app_state.kill_switch_engaged = False
            self._persist_settings()
            self._task = asyncio.create_task(self._run_loop())
        await self._bus.publish(level="INFO", category="SYSTEM", message="Engine started")
        return {"ok": True, "message": "started"}

    async def stop(self) -> dict[str, Any]:
        async with self._lock:
            if not self._status.running:
                return {"ok": True, "message": "already stopped"}
            self._status.running = False
            self._status.entries_paused = False
        await self._bus.publish(level="WARNING", category="SYSTEM", message="Engine stopped")
        return {"ok": True, "message": "stopped"}

    async def pause_entries(self) -> dict[str, Any]:
        self._status.entries_paused = True
        await self._bus.publish(level="WARNING", category="RISK", message="Entries paused")
        return {"ok": True}

    async def resume_entries(self) -> dict[str, Any]:
        self._status.entries_paused = False
        await self._bus.publish(level="INFO", category="RISK", message="Entries resumed")
        return {"ok": True}

    async def flatten(self) -> dict[str, Any]:
        self._positions.clear()
        await self._bus.publish(level="WARNING", category="POSITION", message="All positions flattened")
        return {"ok": True}

    async def kill_switch(self) -> dict[str, Any]:
        self._status.kill_switch_engaged = True
        self._status.running = False
        self._status.entries_paused = True
        self._positions.clear()
        self._orders.clear()
        self._app_state.kill_switch_engaged = True
        self._persist_settings()
        await self._bus.publish(level="ERROR", category="RISK", message="Kill switch engaged")
        return {"ok": True}

    async def get_status(self) -> dict[str, Any]:
        if self._status.running and self._status.started_at:
            start = datetime.fromisoformat(self._status.started_at)
            self._status.uptime_seconds = int((datetime.now(timezone.utc) - start).total_seconds())
        self._status.ws_latency_ms = random.randint(18, 60)
        return self._status.model_dump()

    async def get_settings(self) -> dict[str, Any]:
        return self._app_state.model_dump(mode="json")

    async def update_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = self._app_state.model_dump(mode="json")
        current.update(payload)
        self._app_state = AppState.model_validate(current)
        self._status.mode = self._app_state.mode.value
        self._persist_settings()
        await self._bus.publish(level="INFO", category="SYSTEM", message="Settings updated", payload=payload)
        return self._app_state.model_dump(mode="json")

    async def get_positions(self) -> list[dict[str, Any]]:
        return list(self._positions)

    async def get_open_orders(self) -> list[dict[str, Any]]:
        return list(self._orders)

    async def get_recent_signals(self) -> list[dict[str, Any]]:
        return list(self._signals)[-50:]

    async def get_journal(self, page: int, page_size: int) -> dict[str, Any]:
        start = max((page - 1) * page_size, 0)
        end = start + page_size
        rows = self._journal[start:end]
        return {"items": rows, "page": page, "page_size": page_size, "total": len(self._journal)}

    async def test_connection(self, mode: str) -> dict[str, Any]:
        msg = f"{mode.upper()} connection OK"
        await self._bus.publish(level="INFO", category="WS", message=msg)
        return {"ok": True, "message": msg}

    async def set_mode(self, mode: str) -> dict[str, Any]:
        self._app_state.mode = Mode(mode.upper())
        self._status.mode = self._app_state.mode.value
        self._persist_settings()
        await self._bus.publish(level="INFO", category="SYSTEM", message=f"Mode changed to {mode.upper()}")
        return {"mode": self._status.mode}

    def _persist_settings(self) -> None:
        save_app_state(path=self._state_path, state=self._app_state)

    async def _run_loop(self) -> None:
        while True:
            if not self._status.running:
                await asyncio.sleep(0.3)
                continue

            symbol = random.choice(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
            correlation_id = str(uuid.uuid4())
            side = random.choice(["BUY", "SELL"])
            price = round(random.uniform(90, 250), 2)
            qty = round(random.uniform(0.01, 0.15), 4)

            signal = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "symbol": symbol,
                "side": side,
                "score": round(random.uniform(0.52, 0.91), 3),
                "reason_codes": ["impulse", "retrace", "regime_ok"],
            }
            self._signals.append(signal)
            self._signals = self._signals[-200:]
            await self._bus.publish(level="INFO", category="SIGNAL", message=f"Signal {side} {symbol}", symbol=symbol, correlation_id=correlation_id, payload=signal)

            if not self._status.entries_paused and not self._status.kill_switch_engaged:
                order = {
                    "id": correlation_id,
                    "symbol": symbol,
                    "type": "MARKET",
                    "side": side,
                    "price": price,
                    "qty": qty,
                    "status": "FILLED",
                }
                self._orders = [order] + self._orders[:99]
                pnl = round(random.uniform(-4.0, 8.0), 2)
                pos = {
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "entry": price,
                    "pnl": pnl,
                    "unrealized": pnl,
                    "duration": random.randint(3, 220),
                }
                self._positions = [p for p in self._positions if p["symbol"] != symbol]
                self._positions.append(pos)
                self._journal.insert(0, {"ts": signal["ts"], "event": "FILL", "symbol": symbol, "side": side, "qty": qty, "price": price})
                self._journal = self._journal[:1000]
                self._status.daily_pnl += pnl
                self._status.balance += pnl
                self._status.equity = self._status.balance + sum(p["unrealized"] for p in self._positions)
                await self._bus.publish(level="INFO", category="ORDER", message=f"Order FILLED {symbol}", symbol=symbol, correlation_id=correlation_id, payload=order)
                await self._bus.publish(level="INFO", category="FILL", message=f"Position updated {symbol}", symbol=symbol, correlation_id=correlation_id, payload=pos)

            if random.random() < 0.07:
                await self._bus.publish(level="WARNING", category="RISK", message="Temporary volatility block", payload={"cooldown_seconds": self._app_state.cooldown_seconds})

            if random.random() < 0.03:
                await self._bus.publish(level="ERROR", category="ERROR", message="Transient exchange timeout", payload={"retrying": True})

            self._last_tick = datetime.now(timezone.utc)
            await asyncio.sleep(1.0)
