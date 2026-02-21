from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone

from PySide6.QtCore import QThread, Signal

from danbot.ui.viewmodels import DashboardState, LiveLogEntry


class EngineWorker(QThread):
    state_update = Signal(object)
    log_event = Signal(object)

    def __init__(self, initial_state: DashboardState) -> None:
        super().__init__()
        self._running = True
        self._trading_enabled = True
        self._state = initial_state

    def run(self) -> None:
        asyncio.run(self._run_loop())

    async def _run_loop(self) -> None:
        tick = 0
        while self._running:
            tick += 1
            self._state.ws_latency_ms = max(10.0, random.gauss(34, 7))
            self._state.impulse_score = min(1.0, max(0.0, self._state.impulse_score + random.uniform(-0.05, 0.08)))
            self._state.spread_bps = max(0.2, random.gauss(1.2, 0.25))
            self._state.metrics_24h_winrate = min(100.0, max(0.0, 62.2 + random.uniform(-1.4, 1.4)))
            self._state.metrics_24h_drawdown = max(0.0, 3.1 + random.uniform(-0.4, 0.6))
            self._state.metrics_24h_profit = 1482.0 + random.uniform(-120.0, 180.0)
            self._state.bot_uptime_seconds += 1
            self._state.strategy_status = "Decay Detected" if tick % 5 else "Impulse Rising"
            self.state_update.emit(self._state)

            if tick % 2 == 0:
                category = random.choice(["SIGNAL", "EXECUTE", "RISK", "EXIT", "INCIDENT", "INFO"])
                self.log_event.emit(
                    LiveLogEntry(
                        ts_iso=datetime.now(timezone.utc).isoformat(),
                        severity=category,
                        category=category,
                        symbol="BTC/USDT",
                        message=f"{category.title()} event processed",
                        metrics={"latency_ms": self._state.ws_latency_ms},
                    )
                )
            await asyncio.sleep(0.5)

    def request_stop(self) -> None:
        self._running = False

    def emergency_kill(self) -> None:
        self._trading_enabled = False
        self._running = False

    @property
    def trading_enabled(self) -> bool:
        return self._trading_enabled
