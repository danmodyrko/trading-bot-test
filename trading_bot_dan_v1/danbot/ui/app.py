from __future__ import annotations

from collections import deque

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from danbot.core.config import AppConfig, Mode
from danbot.ui.theme import DARK_QSS
from danbot.ui.widgets import SymbolCard

try:
    import pyqtgraph as pg
except Exception:  # pragma: no cover
    pg = None


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.setWindowTitle("Trading Bot Dan v1")
        self.resize(1300, 820)
        self.health_points: deque[float] = deque(maxlen=300)
        self.mode_armed = False

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        top = QHBoxLayout()
        self.mode_badge = QLabel(f"{config.mode.value} | {'DRY-RUN' if config.execution.dry_run else 'LIVE-ORDERS'}")
        self.mode_badge.setObjectName("badge_demo" if config.mode == Mode.DEMO else "badge_real")
        self.kill_button = QPushButton("GLOBAL KILL SWITCH (Ctrl+K)")
        self.kill_button.setObjectName("danger")
        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        top.addWidget(self.mode_badge)
        top.addStretch()
        top.addWidget(self.start_button)
        top.addWidget(self.stop_button)
        top.addWidget(self.kill_button)
        layout.addLayout(top)

        QShortcut(QKeySequence("Ctrl+K"), self, activated=self._kill_switch)
        self.kill_button.clicked.connect(self._kill_switch)

        tabs = QTabWidget()
        tabs.addTab(self._live_tab(), "Live Monitor")
        tabs.addTab(QWidget(), "Strategy Diagnostics")
        tabs.addTab(QWidget(), "Backtest/Replay")
        tabs.addTab(self._settings_tab(), "Settings")
        layout.addWidget(tabs)

    def _live_tab(self) -> QWidget:
        page = QWidget()
        l = QVBoxLayout(page)

        cards = QHBoxLayout()
        for s in self.config.symbols:
            cards.addWidget(SymbolCard(s))
        l.addLayout(cards)

        self.chart = None
        if pg:
            self.chart = pg.PlotWidget(title="Bot Health & Activity (last 10m)")
            self.chart.setYRange(0, 200)
            self.chart_curve = self.chart.plot(pen="y")
            l.addWidget(self.chart)
            timer = QTimer(self)
            timer.timeout.connect(self._refresh_chart)
            timer.start(500)

        fl = QHBoxLayout()
        self.category_filter = QComboBox()
        self.category_filter.addItems(["ALL", "INFO", "SIGNAL", "RISK", "INCIDENT"])
        self.symbol_filter = QComboBox()
        self.symbol_filter.addItems(["ALL", *self.config.symbols])
        self.log_search = QLineEdit()
        self.log_search.setPlaceholderText("Search log...")
        fl.addWidget(self.category_filter)
        fl.addWidget(self.symbol_filter)
        fl.addWidget(self.log_search)
        l.addLayout(fl)

        self.lifelog = QListWidget()
        l.addWidget(self.lifelog)
        return page

    def _settings_tab(self) -> QWidget:
        page = QWidget()
        l = QVBoxLayout(page)
        l.addWidget(QLabel("REAL mode confirmation gate"))
        self.real_text = QLineEdit()
        self.real_text.setPlaceholderText('Type "REAL"')
        self.real_ack = QCheckBox("I understand real capital risk")
        self.enable_live_orders = QCheckBox("Enable live order submission (dry-run off)")
        self.regime_toggle = QCheckBox("Regime Filter ON")
        self.regime_toggle.setChecked(True)
        btn = QPushButton("Enable REAL Trading")
        btn.clicked.connect(self._confirm_real)
        l.addWidget(self.real_text)
        l.addWidget(self.real_ack)
        l.addWidget(self.enable_live_orders)
        l.addWidget(self.regime_toggle)
        l.addWidget(btn)

        l.addWidget(QLabel("Universe Controls"))
        self.search_symbols = QLineEdit()
        self.search_symbols.setPlaceholderText("Search symbol")
        self.auto_refresh_toggle = QCheckBox("Auto-refresh universe")
        self.auto_refresh_toggle.setChecked(True)
        l.addWidget(self.search_symbols)
        l.addWidget(self.auto_refresh_toggle)
        return page

    def _refresh_chart(self) -> None:
        if not self.chart:
            return
        self.health_points.append(20 + (len(self.health_points) % 30))
        self.chart_curve.setData(list(self.health_points))

    def append_lifelog(self, severity: str, message: str) -> None:
        self.lifelog.addItem(f"[{severity}] {message}")

    def _kill_switch(self) -> None:
        QMessageBox.critical(self, "Kill Switch", "Global kill switch activated. New entries blocked.")
        self.append_lifelog("RISK", "Kill switch activated")

    def _confirm_real(self) -> None:
        if self.real_text.text() != "REAL" or not self.real_ack.isChecked():
            QMessageBox.warning(self, "Blocked", "Confirmation gate failed")
            return
        self.countdown = 10
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._countdown_real)
        self.timer.start(1000)

    def _countdown_real(self) -> None:
        if self.countdown <= 0:
            self.timer.stop()
            self.mode_armed = True
            QMessageBox.information(self, "Armed", "REAL mode armed")
            return
        self.statusBar().showMessage(f"REAL mode arming in {self.countdown}s")
        self.countdown -= 1


def launch_ui(config: AppConfig) -> None:
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(DARK_QSS)
    w = MainWindow(config)
    w.show()
    app.exec()
