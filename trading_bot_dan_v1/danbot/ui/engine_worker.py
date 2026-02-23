from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from PySide6.QtCore import QThread, Signal

from danbot.core.config import AppConfig, AppState, Mode
from danbot.core.events import EventRecord, get_event_bus
from danbot.exchange.adapter import ExchangeAdapter, NotConfiguredError, TimeSync
from danbot.storage.db import Database
from danbot.ui.viewmodels import DashboardState, LiveLogEntry


class EngineWorker(QThread):
    state_update = Signal(object)
    log_event = Signal(object)

    def __init__(self, config: AppConfig, app_state: AppState, db: Database, demo_key: str, demo_secret: str, real_key: str, real_secret: str, time_sync: TimeSync | None = None) -> None:
        super().__init__()
        self._running = True
        self._trading_enabled = True
        self._config = config
        self._app_state = app_state
        self._db = db
        self._events = get_event_bus()
        mode = Mode(self._app_state.mode)
        self._adapter = ExchangeAdapter(mode=mode, api_key=demo_key if mode == Mode.DEMO else real_key, api_secret=demo_secret if mode == Mode.DEMO else real_secret, time_sync=time_sync or TimeSync())
        self._state = DashboardState(mode=mode.value, dry_run=app_state.dry_run, risk_pct=app_state.max_daily_loss_pct, api_configured=self._adapter.configured)
        self._last_lifelog_seen = 0

    def run(self) -> None:
        asyncio.run(self._run_loop())

    async def _run_loop(self) -> None:
        self._events.publish(EventRecord(action="ENGINE_START", message="worker started", category="INFO"))
        try:
            await self._adapter.ensure_mode(Mode(self._app_state.mode))
        except NotConfiguredError:
            self._emit_log("INCIDENT", "INCIDENT", "API NOT CONFIGURED", action="API_ERROR")
        except Exception as exc:
            self._emit_log("INCIDENT", "INCIDENT", f"time sync failed: {exc}", action="API_ERROR")
        self._emit_log("INFO", "INFO", "engine running", action="ENGINE_RUNNING")
        tick = 0
        while self._running:
            tick += 1
            self._state.bot_uptime_seconds += 1
            await self._refresh_latency()
            if tick % 2 == 0:
                await self._refresh_balance()
            if tick % 5 == 0:
                self._refresh_trade_metrics()
            self._pull_lifelog_events()
            self.state_update.emit(self._state)
            await asyncio.sleep(1)
        self._emit_log("INFO", "INFO", "engine stopped", action="ENGINE_STOP")

    async def _refresh_latency(self) -> None:
        try:
            self._state.ws_latency_ms = await self._adapter.ping_latency_ms()
        except Exception as exc:
            self._emit_log("INCIDENT", "INCIDENT", f"WS stale/reconnect required: {exc}", action="WS_STALE")

    async def _refresh_balance(self) -> None:
        if not self._adapter.configured:
            self._state.current_balance_usdt = None
            return
        try:
            overview = await self._adapter.get_account_overview()
            self._state.current_balance_usdt = float(overview["balance_usdt"])
        except NotConfiguredError:
            self._emit_log("INCIDENT", "INCIDENT", "API NOT CONFIGURED", action="API_ERROR")
            self._state.current_balance_usdt = None
        except Exception as exc:
            self._emit_log("INCIDENT", "RISK", f"account refresh failed: {exc}", action="API_ERROR")

    def _refresh_trade_metrics(self) -> None:
        metrics = self._db.closed_trade_metrics_24h()
        self._state.metrics_24h_winrate = metrics["winrate"]
        self._state.metrics_24h_drawdown = metrics["drawdown"]
        self._state.metrics_24h_profit = metrics["profit"]

    def _pull_lifelog_events(self) -> None:
        rows = self._db.conn.execute("SELECT id,ts,severity,category,symbol,message,json_metrics FROM lifelog WHERE id > ? ORDER BY id ASC", (self._last_lifelog_seen,)).fetchall()
        for row in rows:
            self._last_lifelog_seen = int(row["id"])
            category = row["category"]
            self.log_event.emit(LiveLogEntry(ts_iso=row["ts"], severity=row["severity"], category=category, symbol=row["symbol"] or None, message=row["message"], metrics={}))
            if category.upper() == "EXIT" and "POSITION CLOSED" in row["message"].upper():
                self._events.publish(EventRecord(action="POSITION_CLOSED", message=row["message"], category="EXIT", severity=row["severity"], symbol=row["symbol"] or None))
                self._refresh_trade_metrics()

    def _emit_log(self, severity: str, category: str, message: str, action: str = "INFO") -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._db.insert_lifelog(now, severity, category, message)
        self.log_event.emit(LiveLogEntry(now, severity, category, None, message, {}))
        self._events.publish(EventRecord(action=action, message=message, severity=severity, category=category))

    def request_stop(self) -> None:
        self._running = False
        self._emit_log("INFO", "INFO", "engine stop requested", action="ENGINE_STOP")

    def emergency_kill(self) -> None:
        self._trading_enabled = False
        self._running = False
        self._emit_log("INCIDENT", "INCIDENT", "KILL SWITCH engaged", action="KILL_SWITCH")

    @property
    def trading_enabled(self) -> bool:
        return self._trading_enabled
