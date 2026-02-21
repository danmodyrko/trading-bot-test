from __future__ import annotations

import functools
from datetime import datetime, timezone

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from danbot.core.config import AppConfig
from danbot.ui.engine_worker import EngineWorker
from danbot.ui.theme import ACCENT_BLUE, ACCENT_GOLD, ACCENT_GREEN, ACCENT_RED, DARK_QSS, GAP, OUTER_PADDING, PRIMARY_BG
from danbot.ui.viewmodels import DashboardState, LiveLogEntry, LiveLogModel
from danbot.ui.widgets_glass import GlassButton, GlassCard, LiveLogPanel, MetricCard, PillBadge, StrategyPanel


def safe_slot(handler):
    @functools.wraps(handler)
    def wrapper(self: MainWindow, *args, **kwargs):
        try:
            return handler(self, *args, **kwargs)
        except Exception as exc:  # pragma: no cover
            self._append_log(
                LiveLogEntry(
                    ts_iso=datetime.now(timezone.utc).isoformat(),
                    severity="INCIDENT",
                    category="INCIDENT",
                    symbol=None,
                    message=f"UI handler error: {exc}",
                )
            )

    return wrapper


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.worker: EngineWorker | None = None
        self.blocked = False
        self.log_model = LiveLogModel()
        self.pending_refresh = False
        self.state = DashboardState(mode=config.mode.value, dry_run=config.execution.dry_run, risk_pct=config.risk.max_trade_risk_pct)

        self.setWindowTitle("Dan v1 Dashboard")
        self.setFixedSize(1440, 820)
        self.setStyleSheet(f"background: {PRIMARY_BG};")

        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(OUTER_PADDING, OUTER_PADDING, OUTER_PADDING, OUTER_PADDING)
        outer.setSpacing(GAP)

        outer.addWidget(self._build_top_bar())

        middle = QHBoxLayout()
        middle.setSpacing(GAP)
        self.strategy_panel = StrategyPanel()
        strategy_card = GlassCard("Strategy")
        strategy_card.set_content(self.strategy_panel)

        self.log_panel = LiveLogPanel()
        log_card = GlassCard("Live Log")
        log_card.set_content(self.log_panel)

        middle.addWidget(strategy_card, 32)
        middle.addWidget(log_card, 68)
        outer.addLayout(middle, 1)

        metrics = QHBoxLayout()
        metrics.setSpacing(GAP)
        self.winrate = MetricCard("24h Win Rate", "--", ACCENT_GREEN, "signal.svg")
        self.drawdown = MetricCard("24h Drawdown", "--", ACCENT_RED, "risk_event.svg")
        self.profit = MetricCard("24h Profit", "--", ACCENT_GOLD, "execute.svg")
        self.uptime = MetricCard("Bot Uptime", "00:00:00", ACCENT_BLUE, "ws.svg")
        metrics.addWidget(self.winrate)
        metrics.addWidget(self.drawdown)
        metrics.addWidget(self.profit)
        metrics.addWidget(self.uptime)
        outer.addLayout(metrics)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._flush_logs)
        self.refresh_timer.start(200)

        self.log_panel.search.textChanged.connect(self._schedule_refresh)
        self.log_panel.severity.currentTextChanged.connect(self._schedule_refresh)

    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        l = QHBoxLayout(bar)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(10)

        self.badge_mode = PillBadge("demo.svg", "DEMO MODE", ACCENT_GREEN)
        self.badge_dry = PillBadge("dryrun.svg", "DRY RUN", ACCENT_GOLD)
        self.badge_ws = PillBadge("ws.svg", "WS OK 0ms", ACCENT_BLUE)
        self.badge_risk = PillBadge("risk.svg", f"RISK {self.state.risk_pct:.2f}%", ACCENT_RED)
        l.addWidget(self.badge_mode)
        l.addWidget(self.badge_dry)
        l.addWidget(self.badge_ws)
        l.addWidget(self.badge_risk)
        l.addStretch()

        self.start_btn = GlassButton("START", "primary")
        self.stop_btn = GlassButton("STOP", "secondary")
        self.kill_btn = GlassButton("KILL SWITCH", "danger")
        self.start_btn.clicked.connect(self.on_start)
        self.stop_btn.clicked.connect(self.on_stop)
        self.kill_btn.clicked.connect(self.on_kill)
        l.addWidget(self.start_btn)
        l.addWidget(self.stop_btn)
        l.addWidget(self.kill_btn)
        return bar

    def _apply_state(self, state: DashboardState) -> None:
        self.strategy_panel.symbol.setText(state.strategy_symbol)
        self.strategy_panel.impulse_val.setText(f"{state.impulse_score:.2f}")
        self.strategy_panel.progress.setValue(int(state.impulse_score * 100))
        self.strategy_panel.spread.setText(f"Spread {state.spread_bps:.1f} bps")
        self.strategy_panel.spread_value.setText(f"{state.spread_bps:.1f}")
        self.strategy_panel.status.setText(state.strategy_status)
        self.badge_ws.layout().itemAt(1).widget().setText(f"WS OK {state.ws_latency_ms:.0f}ms")

        self.winrate.set_value("--" if state.metrics_24h_winrate is None else f"{state.metrics_24h_winrate:.1f}%")
        self.drawdown.set_value("--" if state.metrics_24h_drawdown is None else f"{state.metrics_24h_drawdown:.1f}%")
        self.profit.set_value("--" if state.metrics_24h_profit is None else f"${state.metrics_24h_profit:,.0f}")
        hours, rem = divmod(state.bot_uptime_seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        self.uptime.set_value(f"{hours:02}:{minutes:02}:{seconds:02}")

    @safe_slot
    def on_start(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        self.blocked = False
        self.worker = EngineWorker(self.state)
        self.worker.state_update.connect(self._on_worker_state)
        self.worker.log_event.connect(self._append_log)
        self.worker.start()
        self._append_log(LiveLogEntry(datetime.now(timezone.utc).isoformat(), "INFO", "INFO", None, "engine start", {}))

    @safe_slot
    def on_stop(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.request_stop()
            self.worker.wait(2000)
            self._append_log(LiveLogEntry(datetime.now(timezone.utc).isoformat(), "INFO", "INFO", None, "engine stop requested", {}))

    @safe_slot
    def on_kill(self) -> None:
        self.blocked = True
        if self.worker and self.worker.isRunning():
            self.worker.emergency_kill()
            self.worker.wait(1000)
        self._append_log(LiveLogEntry(datetime.now(timezone.utc).isoformat(), "INCIDENT", "INCIDENT", None, "KILL SWITCH: trading blocked", {}))

    def _on_worker_state(self, state: DashboardState) -> None:
        self.state = state
        self._apply_state(state)

    def _append_log(self, entry: LiveLogEntry) -> None:
        self.log_model.append(entry)
        self.pending_refresh = True

    def _schedule_refresh(self) -> None:
        self.pending_refresh = True

    def _flush_logs(self) -> None:
        if not self.pending_refresh:
            return
        self.pending_refresh = False
        rows = self.log_model.get_filtered(
            self.log_panel.severity.currentText(),
            self.log_panel.search.text(),
        )
        self.log_panel.set_entries(rows)


def launch_ui(config: AppConfig) -> None:
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(DARK_QSS)
    w = MainWindow(config)
    w.show()
    app.exec()
