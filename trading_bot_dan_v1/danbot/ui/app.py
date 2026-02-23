from __future__ import annotations

import asyncio
import functools
import os
import traceback
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from danbot.core.config import AppConfig, AppState, Mode, load_app_state, save_app_state
from danbot.core.events import EventRecord, get_event_bus
from danbot.core.presets import PRESETS, apply_preset, detect_profile
from danbot.exchange.adapter import ExchangeAdapter, NotConfiguredError, TimeSync
from danbot.storage.db import Database
from danbot.ui.engine_worker import EngineWorker
from danbot.ui.theme import ACCENT_BLUE, ACCENT_GOLD, ACCENT_GREEN, ACCENT_RED, DARK_QSS, GAP, OUTER_PADDING, PRIMARY_BG
from danbot.ui.viewmodels import LiveLogEntry, LiveLogModel
from danbot.ui.widgets_glass import GlassButton, LiveLogPanel, MetricCard, PillBadge, SettingsPanel, SettingsWindow, svg_pixmap


class ConnectionTestWorker(QThread):
    connection_result = Signal(bool, str)

    def __init__(self, mode: Mode, key: str, secret: str, time_sync: TimeSync) -> None:
        super().__init__()
        self.mode = mode
        self.key = key
        self.secret = secret
        self.time_sync = time_sync

    def run(self) -> None:
        adapter = ExchangeAdapter(mode=self.mode, api_key=self.key, api_secret=self.secret, time_sync=self.time_sync)
        try:
            overview = asyncio.run(self._run_test(adapter))
            self.connection_result.emit(True, f"{self.mode.value} connection OK — Balance: {overview.get('balance_usdt', 0):.2f} USDT")
        except NotConfiguredError:
            self.connection_result.emit(False, f"{self.mode.value} connection failed — API NOT CONFIGURED")
        except Exception as exc:
            self.connection_result.emit(False, f"{self.mode.value} connection failed — {exc}")

    async def _run_test(self, adapter: ExchangeAdapter) -> dict[str, float | int]:
        await adapter.ensure_mode(self.mode)
        return await adapter.get_account_overview()


def safe_slot(handler):
    @functools.wraps(handler)
    def wrapper(self: MainWindow, *args, **kwargs):
        try:
            return handler(self, *args, **kwargs)
        except Exception as exc:  # pragma: no cover
            self.event_bus.incident(
                action="UI_EXCEPTION",
                message=f"UI handler error: {exc}",
                details={"handler": handler.__name__, "trace": traceback.format_exc(limit=5)},
            )

    return wrapper


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.db = Database(config.storage.sqlite_path)
        self.db.init(Path(__file__).resolve().parents[1] / "storage" / "schema.sql")
        self.event_bus = get_event_bus()
        self.app_state = load_app_state(config.storage.app_state_path)
        self.worker: EngineWorker | None = None
        self.log_model = LiveLogModel(max_entries=2000)
        self.pending_refresh = False
        self._updating_form = False
        self._custom_log_emitted = False
        self._preset_baseline = self._current_profile_values(self.app_state)
        self._connection_workers: list[ConnectionTestWorker] = []
        self._time_sync = TimeSync()

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
        outer.addWidget(self.log_panel, 1)

        self.settings = SettingsPanel()
        self.settings_window = SettingsWindow(self.settings, self)
        self.settings_window.close_btn.clicked.connect(self.settings_window.close)
        self._bind_settings()

        metrics = QHBoxLayout()
        metrics.setSpacing(GAP)
        self.winrate = MetricCard("24h Win Rate", "--", ACCENT_GREEN)
        self.drawdown = MetricCard("24h Drawdown", "--", ACCENT_RED)
        self.profit = MetricCard("24h Profit", "--", ACCENT_GOLD)
        self.uptime = MetricCard("Bot Uptime", "00:00:00", ACCENT_BLUE)
        self.balance = MetricCard("Current Balance", "NOT CONFIGURED", ACCENT_BLUE)
        for c in [self.winrate, self.drawdown, self.profit, self.uptime, self.balance]:
            metrics.addWidget(c)
        outer.addLayout(metrics)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._flush_logs)
        self.refresh_timer.start(120)

        self.latency_timer = QTimer(self)
        self.latency_timer.timeout.connect(self._refresh_latency_badge)
        self.latency_timer.start(1000)

        self._load_logs_from_db()
        self._refresh_control_state()

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
        self.settings_btn = GlassButton("SETTINGS")
        self.settings_btn.setIcon(QIcon(svg_pixmap("gear.svg", 14, ACCENT_BLUE)))
        self.start_btn.clicked.connect(self.on_start)
        self.stop_btn.clicked.connect(self.on_stop)
        self.kill_btn.clicked.connect(self.on_kill)
        self.settings_btn.clicked.connect(self.open_settings)
        l.addWidget(self.start_btn)
        l.addWidget(self.stop_btn)
        l.addWidget(self.kill_btn)
        l.addWidget(self.settings_btn)
        return bar

    def _bind_settings(self) -> None:
        self._load_env_into_form()
        self._set_form_from_state(self.app_state)
        self.settings.save_btn.clicked.connect(lambda: self._on_settings_button("SAVE", True))
        self.settings.apply_btn.clicked.connect(lambda: self._on_settings_button("APPLY", False))
        self.settings.test_demo_btn.clicked.connect(lambda: self._test_connection(Mode.DEMO))
        self.settings.test_real_btn.clicked.connect(lambda: self._test_connection(Mode.REAL))
        for name, btn in self.settings.preset_buttons.items():
            btn.clicked.connect(lambda _=False, preset=name: self.on_apply_preset(preset))
        self._connect_auto_custom_tracking()

    @safe_slot
    def _on_settings_button(self, label: str, persist: bool) -> None:
        self.event_bus.publish(EventRecord(action="UI_CLICK", message=f"UI: {label} pressed"))
        self.on_save_settings()
        action = "SETTINGS_CHANGED" if persist else "PRESET_APPLIED"
        self.event_bus.publish(EventRecord(action=action, message=f"Settings {label.lower()} complete"))

    def _connect_auto_custom_tracking(self) -> None:
        widgets = [
            self.settings.mode_combo,
            self.settings.dry_run,
            self.settings.order_value,
            self.settings.max_lev,
            self.settings.max_pos,
            self.settings.max_loss,
            self.settings.cooldown,
            self.settings.spread,
            self.settings.slippage,
            self.settings.edge_gate,
            self.settings.vol_kill,
            self.settings.regime,
            self.settings.regime_thr,
            self.settings.max_tph,
            self.settings.impulse_pct,
            self.settings.impulse_window,
            self.settings.exhaustion,
            self.settings.tp_profile,
            self.settings.time_stop,
            self.settings.stop_model,
            self.settings.spike_toggle,
            self.settings.ml_toggle,
            self.settings.ml_threshold,
            self.settings.model_path,
        ]
        for widget in widgets:
            signal = getattr(widget, "valueChanged", None) or getattr(widget, "textChanged", None) or getattr(widget, "currentTextChanged", None) or getattr(widget, "stateChanged", None) or getattr(widget, "toggled", None)
            if signal is not None:
                signal.connect(self._on_manual_setting_change)

    def _load_env_into_form(self) -> None:
        self.settings.demo_key.setText(os.getenv("BINANCE_TESTNET_API_KEY", ""))
        self.settings.demo_secret.setText(os.getenv("BINANCE_TESTNET_API_SECRET", ""))
        self.settings.real_key.setText(os.getenv("BINANCE_API_KEY", ""))
        self.settings.real_secret.setText(os.getenv("BINANCE_API_SECRET", ""))

    def _set_form_from_state(self, state: AppState) -> None:
        s = self.settings
        self._updating_form = True
        s.mode_combo.setCurrentText(state.mode.value)
        s.dry_run.setChecked(state.dry_run)
        s.kill_status.setText("ENGAGED" if state.kill_switch_engaged else "OFF")
        s.order_value.setValue(state.order_value_pct_balance)
        s.max_lev.setValue(state.max_leverage)
        s.max_pos.setValue(state.max_positions)
        s.max_loss.setValue(state.max_daily_loss_pct)
        s.cooldown.setValue(state.cooldown_seconds)
        s.spread.setValue(state.spread_guard_bps)
        s.slippage.setValue(state.max_slippage_bps)
        s.edge_gate.setValue(state.edge_gate_factor)
        s.vol_kill.setValue(state.vol_10s_threshold)
        s.regime.setChecked(state.regime_filter_enabled)
        s.regime_thr.setValue(state.trend_strength_threshold)
        s.max_tph.setValue(state.max_trades_per_hour)
        s.impulse_pct.setValue(state.impulse_threshold_pct)
        s.impulse_window.setValue(state.impulse_window_seconds)
        s.exhaustion.setValue(state.exhaustion_ratio_threshold)
        s.tp_profile.setText(",".join(str(v) for v in state.tp_profile))
        s.time_stop.setValue(state.time_stop_seconds)
        s.stop_model.setCurrentText(state.stop_model)
        s.spike_toggle.setChecked(state.spike_classifier_enabled)
        s.ml_toggle.setChecked(state.ml_gate_enabled)
        s.ml_threshold.setValue(state.ml_threshold)
        s.model_path.setText(state.ml_model_path)
        profile = state.active_profile if state.active_profile in PRESETS else detect_profile(state)
        state.active_profile = profile
        s.set_active_profile(profile)
        self._updating_form = False

    def _parse_tp_profile(self, raw: str) -> list[float]:
        values = [chunk.strip() for chunk in raw.split(",") if chunk.strip()]
        return [float(v) for v in values] if values else [0.3, 0.5, 0.6]

    def _state_from_form(self) -> AppState:
        return AppState(
            mode=Mode(self.settings.mode_combo.currentText()),
            dry_run=self.settings.dry_run.isChecked(),
            kill_switch_engaged=self.app_state.kill_switch_engaged,
            active_profile=self.settings.active_profile_label.text().replace("Active profile: ", ""),
            order_value_pct_balance=self.settings.order_value.value(),
            max_leverage=self.settings.max_lev.value(),
            max_positions=self.settings.max_pos.value(),
            max_daily_loss_pct=self.settings.max_loss.value(),
            cooldown_seconds=self.settings.cooldown.value(),
            max_trades_per_hour=self.settings.max_tph.value(),
            spread_guard_bps=self.settings.spread.value(),
            max_slippage_bps=self.settings.slippage.value(),
            edge_gate_factor=self.settings.edge_gate.value(),
            vol_10s_threshold=self.settings.vol_kill.value(),
            regime_filter_enabled=self.settings.regime.isChecked(),
            trend_strength_threshold=self.settings.regime_thr.value(),
            time_stop_seconds=self.settings.time_stop.value(),
            tp_profile=self._parse_tp_profile(self.settings.tp_profile.text()),
            impulse_threshold_pct=self.settings.impulse_pct.value(),
            impulse_window_seconds=self.settings.impulse_window.value(),
            exhaustion_ratio_threshold=self.settings.exhaustion.value(),
            stop_model=self.settings.stop_model.currentText(),
            spike_classifier_enabled=self.settings.spike_toggle.isChecked(),
            ml_gate_enabled=self.settings.ml_toggle.isChecked(),
            ml_threshold=self.settings.ml_threshold.value(),
            ml_model_path=self.settings.model_path.text().strip(),
        )

    def _current_profile_values(self, state: AppState) -> dict[str, object]:
        return {field: getattr(state, field) for field in PRESETS["SAFE"].keys()}

    @safe_slot
    def _on_manual_setting_change(self, *_args) -> None:
        if self._updating_form:
            return
        current_state = self._state_from_form()
        current_values = self._current_profile_values(current_state)
        matched = detect_profile(current_state)
        if matched != "CUSTOM":
            self.settings.set_active_profile(matched)
            self.app_state.active_profile = matched
        elif current_values != self._preset_baseline:
            self.settings.set_active_profile("CUSTOM")
            self.app_state.active_profile = "CUSTOM"
            if not self._custom_log_emitted:
                self.event_bus.publish(EventRecord(action="SETTINGS_CHANGED", message="Profile switched to CUSTOM (manual change)"))
                self._custom_log_emitted = True
        self.on_save_settings()

    @safe_slot
    def on_apply_preset(self, preset_name: str) -> None:
        self.event_bus.publish(EventRecord(action="UI_CLICK", message=f"UI: PRESET {preset_name} pressed"))
        self.app_state = apply_preset(self.app_state, preset_name)
        self.app_state.active_profile = preset_name
        self._preset_baseline = self._current_profile_values(self.app_state)
        self._custom_log_emitted = False
        self._set_form_from_state(self.app_state)
        self.on_save_settings()
        self.event_bus.publish(EventRecord(action="PRESET_APPLIED", message=f"Preset applied: {preset_name}", details={"preset": preset_name}))

    def _credentials_for_mode(self, mode: Mode) -> tuple[str, str]:
        if mode == Mode.DEMO:
            return self.settings.demo_key.text().strip(), self.settings.demo_secret.text().strip()
        return self.settings.real_key.text().strip(), self.settings.real_secret.text().strip()

    def _save_env(self) -> None:
        lines = {
            "BINANCE_TESTNET_API_KEY": self.settings.demo_key.text().strip(),
            "BINANCE_TESTNET_API_SECRET": self.settings.demo_secret.text().strip(),
            "BINANCE_API_KEY": self.settings.real_key.text().strip(),
            "BINANCE_API_SECRET": self.settings.real_secret.text().strip(),
        }
        for key, value in lines.items():
            os.environ[key] = value
        content = "\n".join(f"{k}={v}" for k, v in lines.items()) + "\n"
        Path(".env").write_text(content, encoding="utf-8")

    @safe_slot
    def on_save_settings(self) -> None:
        prev_mode = self.app_state.mode
        self.app_state = self._state_from_form()
        save_app_state(self.config.storage.app_state_path, self.app_state)
        self._save_env()
        self.badge_mode.text_lbl.setText(f"{self.app_state.mode.value} MODE")
        self.badge_mode.icon_lbl.setPixmap(svg_pixmap("demo.svg", 14, ACCENT_GREEN if self.app_state.mode == Mode.DEMO else ACCENT_RED))
        self.badge_dry.text_lbl.setText("DRY RUN ON" if self.app_state.dry_run else "DRY RUN OFF")
        self.badge_risk.text_lbl.setText(f"RISK {self.app_state.max_daily_loss_pct:.2f}%")
        self.settings.kill_status.setText("ENGAGED" if self.app_state.kill_switch_engaged else "OFF")
        self.event_bus.publish(EventRecord(action="SETTINGS_CHANGED", message="Settings saved/applied", details={"mode": self.app_state.mode.value, "dry_run": self.app_state.dry_run}))
        self._refresh_control_state()
        if prev_mode != self.app_state.mode:
            self._sync_time_for_current_mode()

    def _sync_time_for_current_mode(self) -> None:
        mode = self.app_state.mode
        key, secret = self._credentials_for_mode(mode)
        if not key or not secret:
            self.event_bus.incident("API_ERROR", "API NOT CONFIGURED", details={"mode": mode.value})
            return

        async def _sync() -> None:
            adapter = ExchangeAdapter(mode=mode, api_key=key, api_secret=secret, time_sync=self._time_sync)
            await adapter.ensure_mode(mode)

        try:
            asyncio.run(_sync())
        except NotConfiguredError:
            self.event_bus.incident("API_ERROR", "API NOT CONFIGURED", details={"mode": mode.value})
        except Exception as exc:
            self.event_bus.incident("API_ERROR", f"time sync failed: {exc}", details={"mode": mode.value})

    @safe_slot
    def _test_connection(self, mode: Mode) -> None:
        self.event_bus.publish(EventRecord(action="UI_CLICK", message=f"UI: Test {mode.value} connection pressed"))
        key, secret = self._credentials_for_mode(mode)
        self.settings.set_connection_status(f"Testing {mode.value} API...", is_error=False)
        worker = ConnectionTestWorker(mode, key, secret, self._time_sync)
        worker.connection_result.connect(lambda success, message, _mode=mode: self._on_connection_test_done(_mode, success, message))
        worker.finished.connect(lambda: self._connection_workers.remove(worker) if worker in self._connection_workers else None)
        self._connection_workers.append(worker)
        worker.start()

    @safe_slot
    def _on_connection_test_done(self, mode: Mode, ok: bool, message: str) -> None:
        self.settings.set_connection_status(message, is_error=not ok)
        severity = "INFO" if ok else "INCIDENT"
        category = "INFO" if ok else "INCIDENT"
        self.event_bus.publish(EventRecord(action="API_CONNECTION_TEST", message=message, severity=severity, category=category, details={"mode": mode.value, "ok": ok}))

    @safe_slot
    def open_settings(self) -> None:
        self.event_bus.publish(EventRecord(action="UI_CLICK", message="UI: SETTINGS pressed"))
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    @safe_slot
    def on_start(self) -> None:
        self.event_bus.publish(EventRecord(action="UI_CLICK", message="UI: START pressed"))
        if self.worker and self.worker.isRunning():
            return
        if self.app_state.mode == Mode.REAL and (self.settings.real_gate.text().strip().upper() != "REAL" or not self.settings.real_confirm.isChecked()):
            self.event_bus.publish(EventRecord(action="ENTRY_BLOCKED", message="REAL gate failed; trading blocked", severity="WARNING", category="RISK", details={"reason": "REAL gate"}))
            return
        self.app_state.kill_switch_engaged = False
        save_app_state(self.config.storage.app_state_path, self.app_state)
        demo_key, demo_secret = self._credentials_for_mode(Mode.DEMO)
        real_key, real_secret = self._credentials_for_mode(Mode.REAL)
        self.worker = EngineWorker(
            self.config,
            self.app_state,
            self.db,
            demo_key,
            demo_secret,
            real_key,
            real_secret,
            self._time_sync,
        )
        self.worker.state_update.connect(self._on_worker_state)
        self.worker.log_event.connect(self._append_log)
        self.worker.finished.connect(self._refresh_control_state)
        self.worker.start()
        self.event_bus.publish(EventRecord(action="ENGINE_START", message="engine worker started"))
        self._refresh_control_state()

    @safe_slot
    def on_stop(self) -> None:
        self.event_bus.publish(EventRecord(action="UI_CLICK", message="UI: STOP pressed"))
        if self.worker and self.worker.isRunning():
            self.worker.request_stop()
            self.worker.wait(2000)
        self._refresh_control_state()

    @safe_slot
    def on_kill(self) -> None:
        self.event_bus.publish(EventRecord(action="UI_CLICK", message="UI: KILL SWITCH pressed"))
        self.app_state.kill_switch_engaged = True
        save_app_state(self.config.storage.app_state_path, self.app_state)
        self.settings.kill_status.setText("ENGAGED")
        if self.worker and self.worker.isRunning():
            self.worker.emergency_kill()
            self.worker.wait(1000)
        self.event_bus.publish(EventRecord(action="KILL_SWITCH", message="KILL SWITCH engaged", severity="INCIDENT", category="INCIDENT"))
        self._refresh_control_state()


    def _refresh_control_state(self) -> None:
        running = bool(self.worker and self.worker.isRunning())
        self.start_btn.setEnabled(not running and not self.app_state.kill_switch_engaged)
        self.stop_btn.setEnabled(running)
        self.kill_btn.setEnabled(running or not self.app_state.kill_switch_engaged)
        self.settings.kill_status.setText("ENGAGED" if self.app_state.kill_switch_engaged else "OFF")

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

    def _flush_logs(self) -> None:
        events = self.event_bus.drain_live_events(limit=300)
        for evt in events:
            self.log_model.append(LiveLogEntry(evt.ts_iso, evt.severity, evt.category, evt.symbol, evt.message, evt.details))
            self.pending_refresh = True
        if not self.pending_refresh:
            return
        self.pending_refresh = False
        self.log_panel.set_entries(self.log_model.entries)


def launch_ui(config: AppConfig) -> None:
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(DARK_QSS)
    w = MainWindow(config)
    w.show()
    app.exec()
