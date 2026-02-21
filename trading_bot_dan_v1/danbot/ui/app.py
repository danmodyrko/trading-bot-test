from __future__ import annotations

import asyncio
import functools
import os
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from danbot.core.config import AppConfig, AppState, Mode, load_app_state, save_app_state
from danbot.exchange.adapter import ExchangeAdapter
from danbot.storage.db import Database
from danbot.ui.engine_worker import EngineWorker
from danbot.ui.theme import ACCENT_BLUE, ACCENT_GOLD, ACCENT_GREEN, ACCENT_RED, DARK_QSS, GAP, OUTER_PADDING, PRIMARY_BG
from danbot.ui.viewmodels import LiveLogEntry, LiveLogModel
from danbot.ui.widgets_glass import DashboardTabs, GlassButton, LiveLogPanel, MetricCard, PillBadge, SettingsPanel


def safe_slot(handler):
    @functools.wraps(handler)
    def wrapper(self: MainWindow, *args, **kwargs):
        try:
            return handler(self, *args, **kwargs)
        except Exception as exc:  # pragma: no cover
            self._append_log(LiveLogEntry(datetime.now(timezone.utc).isoformat(), "INCIDENT", "INCIDENT", None, f"UI handler error: {exc}", {}))

    return wrapper


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.db = Database(config.storage.sqlite_path)
        self.db.init(Path(__file__).resolve().parents[1] / "storage" / "schema.sql")
        self.app_state = load_app_state(config.storage.app_state_path)
        self.worker: EngineWorker | None = None
        self.log_model = LiveLogModel(max_entries=2000)
        self.pending_refresh = False

        self.setWindowTitle("Dan v1 Dashboard")
        self.setFixedSize(1440, 820)
        self.setStyleSheet(f"background: {PRIMARY_BG};")

        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(OUTER_PADDING, OUTER_PADDING, OUTER_PADDING, OUTER_PADDING)
        outer.setSpacing(GAP)

        outer.addWidget(self._build_top_bar())

        self.log_panel = LiveLogPanel()
        self.settings = SettingsPanel()
        self._bind_settings()
        self.tabs = DashboardTabs(self.log_panel, self.settings)
        outer.addWidget(self.tabs, 1)

        metrics = QHBoxLayout()
        metrics.setSpacing(GAP)
        self.winrate = MetricCard("24h Win Rate", "--", ACCENT_GREEN)
        self.drawdown = MetricCard("24h Drawdown", "--", ACCENT_RED)
        self.profit = MetricCard("24h Profit", "--", ACCENT_GOLD)
        self.uptime = MetricCard("Bot Uptime", "00:00:00", ACCENT_BLUE)
        self.balance = MetricCard("Current Balance (USDT)", "NOT CONFIGURED", ACCENT_BLUE)
        for c in [self.winrate, self.drawdown, self.profit, self.uptime, self.balance]:
            metrics.addWidget(c)
        outer.addLayout(metrics)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._flush_logs)
        self.refresh_timer.start(200)
        self.log_panel.search.textChanged.connect(self._schedule_refresh)
        self.log_panel.severity.currentTextChanged.connect(self._schedule_refresh)

        self.latency_timer = QTimer(self)
        self.latency_timer.timeout.connect(self._refresh_latency_badge)
        self.latency_timer.start(1000)

        self._load_logs_from_db()

    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        l = QHBoxLayout(bar)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(10)
        self.badge_mode = PillBadge("demo.svg", f"{self.app_state.mode.value} MODE", ACCENT_GREEN if self.app_state.mode == Mode.DEMO else ACCENT_RED)
        self.badge_dry = PillBadge("dryrun.svg", "DRY RUN ON" if self.app_state.dry_run else "DRY RUN OFF", ACCENT_GOLD)
        self.badge_ws = PillBadge("ws.svg", "WS OK 0ms", ACCENT_BLUE)
        self.badge_risk = PillBadge("risk.svg", f"RISK {self.app_state.max_daily_loss_pct:.2f}%", ACCENT_RED)
        for w in [self.badge_mode, self.badge_dry, self.badge_ws, self.badge_risk]:
            l.addWidget(w)
        l.addStretch()
        self.start_btn = GlassButton("START", "primary")
        self.stop_btn = GlassButton("STOP")
        self.kill_btn = GlassButton("KILL SWITCH", "danger")
        self.start_btn.clicked.connect(self.on_start)
        self.stop_btn.clicked.connect(self.on_stop)
        self.kill_btn.clicked.connect(self.on_kill)
        l.addWidget(self.start_btn); l.addWidget(self.stop_btn); l.addWidget(self.kill_btn)
        return bar

    def _bind_settings(self) -> None:
        s = self.settings
        s.mode_combo.setCurrentText(self.app_state.mode.value)
        s.dry_run.setChecked(self.app_state.dry_run)
        s.kill_status.setText("ENGAGED" if self.app_state.kill_switch_engaged else "OFF")
        s.order_value.setValue(self.app_state.order_value_usdt)
        s.max_lev.setValue(self.app_state.max_leverage)
        s.max_pos.setValue(self.app_state.max_positions_open)
        s.max_loss.setValue(self.app_state.max_daily_loss_pct)
        s.cooldown.setValue(self.app_state.cooldown_seconds_per_symbol)
        s.spread.setValue(self.app_state.spread_guard_bps)
        s.slippage.setValue(self.app_state.max_slippage_bps)
        s.vol_kill.setValue(self.app_state.volatility_kill_switch_threshold)
        s.regime.setChecked(self.app_state.regime_filter_enabled)
        s.regime_thr.setValue(self.app_state.regime_threshold)
        s.max_tph.setValue(self.app_state.max_trades_per_hour)
        s.impulse_pct.setValue(self.app_state.impulse_threshold_pct)
        s.impulse_window.setValue(self.app_state.impulse_window_seconds)
        s.exhaustion.setValue(self.app_state.exhaustion_ratio_threshold)
        s.tp1.setValue(self.app_state.tp1_pct); s.tp2.setValue(self.app_state.tp2_pct); s.tp3.setValue(self.app_state.tp3_pct)
        s.time_stop.setValue(self.app_state.time_stop_seconds)
        s.stop_model.setCurrentText(self.app_state.stop_model)
        s.spike_toggle.setChecked(self.app_state.spike_classifier_enabled)
        s.ml_toggle.setChecked(self.app_state.ml_gate_enabled)
        s.ml_threshold.setValue(self.app_state.ml_threshold)
        s.model_path.setText(self.app_state.ml_model_path)

        s.save_btn.clicked.connect(self.on_save_settings)
        s.apply_btn.clicked.connect(self.on_save_settings)
        s.test_demo_btn.clicked.connect(lambda: self._test_connection(Mode.DEMO))
        s.test_real_btn.clicked.connect(lambda: self._test_connection(Mode.REAL))

    def _save_env(self) -> None:
        lines = {
            "BINANCE_TESTNET_API_KEY": self.settings.demo_key.text().strip(),
            "BINANCE_TESTNET_API_SECRET": self.settings.demo_secret.text().strip(),
            "BINANCE_API_KEY": self.settings.real_key.text().strip(),
            "BINANCE_API_SECRET": self.settings.real_secret.text().strip(),
        }
        content = "\n".join(f"{k}={v}" for k, v in lines.items()) + "\n"
        Path(".env").write_text(content, encoding="utf-8")

    @safe_slot
    def on_save_settings(self) -> None:
        self.app_state = AppState(
            mode=Mode(self.settings.mode_combo.currentText()),
            dry_run=self.settings.dry_run.isChecked(),
            kill_switch_engaged=self.app_state.kill_switch_engaged,
            order_value_usdt=self.settings.order_value.value(),
            max_leverage=self.settings.max_lev.value(),
            max_positions_open=self.settings.max_pos.value(),
            max_daily_loss_pct=self.settings.max_loss.value(),
            cooldown_seconds_per_symbol=self.settings.cooldown.value(),
            spread_guard_bps=self.settings.spread.value(),
            max_slippage_bps=self.settings.slippage.value(),
            volatility_kill_switch_threshold=self.settings.vol_kill.value(),
            regime_filter_enabled=self.settings.regime.isChecked(),
            regime_threshold=self.settings.regime_thr.value(),
            max_trades_per_hour=self.settings.max_tph.value(),
            impulse_threshold_pct=self.settings.impulse_pct.value(),
            impulse_window_seconds=self.settings.impulse_window.value(),
            exhaustion_ratio_threshold=self.settings.exhaustion.value(),
            tp1_pct=self.settings.tp1.value(),
            tp2_pct=self.settings.tp2.value(),
            tp3_pct=self.settings.tp3.value(),
            time_stop_seconds=self.settings.time_stop.value(),
            stop_model=self.settings.stop_model.currentText(),
            spike_classifier_enabled=self.settings.spike_toggle.isChecked(),
            ml_gate_enabled=self.settings.ml_toggle.isChecked(),
            ml_threshold=self.settings.ml_threshold.value(),
            ml_model_path=self.settings.model_path.text().strip(),
        )
        save_app_state(self.config.storage.app_state_path, self.app_state)
        self._save_env()
        self.badge_mode.text_lbl.setText(f"{self.app_state.mode.value} MODE")
        self.badge_dry.text_lbl.setText("DRY RUN ON" if self.app_state.dry_run else "DRY RUN OFF")
        self._append_log(LiveLogEntry(datetime.now(timezone.utc).isoformat(), "INFO", "INFO", None, "settings saved", {}))

    def _test_connection(self, mode: Mode) -> None:
        key = os.getenv("BINANCE_TESTNET_API_KEY", "") if mode == Mode.DEMO else os.getenv("BINANCE_API_KEY", "")
        secret = os.getenv("BINANCE_TESTNET_API_SECRET", "") if mode == Mode.DEMO else os.getenv("BINANCE_API_SECRET", "")
        adapter = ExchangeAdapter(mode=mode, api_key=key, api_secret=secret)
        try:
            asyncio.run(adapter.get_account_overview())
            self._append_log(LiveLogEntry(datetime.now(timezone.utc).isoformat(), "INFO", "INFO", None, f"{mode.value} API connection success", {}))
        except Exception as exc:
            self._append_log(LiveLogEntry(datetime.now(timezone.utc).isoformat(), "INCIDENT", "INCIDENT", None, f"{mode.value} API connection failed: {exc}", {}))

    @safe_slot
    def on_start(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        if self.app_state.mode == Mode.REAL and (self.settings.real_gate.text().strip().upper() != "REAL" or not self.settings.real_confirm.isChecked()):
            self._append_log(LiveLogEntry(datetime.now(timezone.utc).isoformat(), "RISK", "RISK", None, "REAL gate failed; trading blocked", {}))
            return
        self.app_state.kill_switch_engaged = False
        save_app_state(self.config.storage.app_state_path, self.app_state)
        self.worker = EngineWorker(
            self.config,
            self.app_state,
            self.db,
            os.getenv("BINANCE_TESTNET_API_KEY", ""),
            os.getenv("BINANCE_TESTNET_API_SECRET", ""),
            os.getenv("BINANCE_API_KEY", ""),
            os.getenv("BINANCE_API_SECRET", ""),
        )
        self.worker.state_update.connect(self._on_worker_state)
        self.worker.log_event.connect(self._append_log)
        self.worker.start()

    @safe_slot
    def on_stop(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.request_stop()
            self.worker.wait(2000)

    @safe_slot
    def on_kill(self) -> None:
        self.app_state.kill_switch_engaged = True
        save_app_state(self.config.storage.app_state_path, self.app_state)
        self.settings.kill_status.setText("ENGAGED")
        if self.worker and self.worker.isRunning():
            self.worker.emergency_kill()
            self.worker.wait(1000)

    def _on_worker_state(self, state) -> None:
        self.badge_ws.text_lbl.setText(f"WS OK {state.ws_latency_ms:.0f}ms")
        self.balance.set_value("NOT CONFIGURED" if state.current_balance_usdt is None else f"{state.current_balance_usdt:,.2f}")
        self.winrate.set_value("--" if state.metrics_24h_winrate is None else f"{state.metrics_24h_winrate:.1f}%")
        self.drawdown.set_value("--" if state.metrics_24h_drawdown is None else f"{state.metrics_24h_drawdown:.2f}")
        self.profit.set_value("--" if state.metrics_24h_profit is None else f"{state.metrics_24h_profit:,.2f}")
        h, rem = divmod(state.bot_uptime_seconds, 3600)
        m, s = divmod(rem, 60)
        self.uptime.set_value(f"{h:02}:{m:02}:{s:02}")

    def _append_log(self, entry: LiveLogEntry) -> None:
        self.log_model.append(entry)
        self.pending_refresh = True

    def _load_logs_from_db(self) -> None:
        for row in self.db.list_recent_lifelog(limit=2000):
            self.log_model.append(LiveLogEntry(row["ts"], row["severity"], row["category"], row["symbol"] or None, row["message"], {}))
        self.pending_refresh = True

    def _refresh_latency_badge(self) -> None:
        self.pending_refresh = True

    def _schedule_refresh(self) -> None:
        self.pending_refresh = True

    def _flush_logs(self) -> None:
        if not self.pending_refresh:
            return
        self.pending_refresh = False
        rows = self.log_model.get_filtered(self.log_panel.severity.currentText(), self.log_panel.search.text())
        self.log_panel.set_entries(rows)


def launch_ui(config: AppConfig) -> None:
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(DARK_QSS)
    w = MainWindow(config)
    w.show()
    app.exec()
