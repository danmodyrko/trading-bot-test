from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.setWindowTitle("Trading Bot Dan v1")
        self.resize(1200, 760)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        top = QHBoxLayout()
        self.mode_badge = QLabel(config.mode.value)
        self.mode_badge.setObjectName("badge_demo" if config.mode == Mode.DEMO else "badge_real")
        self.kill_button = QPushButton("KILL SWITCH (Ctrl+K)")
        self.kill_button.setObjectName("danger")
        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        top.addWidget(self.mode_badge)
        top.addStretch()
        top.addWidget(self.start_button)
        top.addWidget(self.stop_button)
        top.addWidget(self.kill_button)
        layout.addLayout(top)

        tabs = QTabWidget()
        tabs.addTab(self._live_tab(), "Live Monitor")
        tabs.addTab(QWidget(), "Strategy Diagnostics")
        tabs.addTab(QWidget(), "Backtest/Replay")
        tabs.addTab(self._settings_tab(), "Settings")
        layout.addWidget(tabs)

    def _live_tab(self) -> QWidget:
        page = QWidget()
        l = QHBoxLayout(page)
        for s in self.config.symbols:
            l.addWidget(SymbolCard(s))
        return page

    def _settings_tab(self) -> QWidget:
        page = QWidget()
        l = QVBoxLayout(page)
        l.addWidget(QLabel("REAL mode confirmation gate"))
        self.real_text = QLineEdit()
        self.real_text.setPlaceholderText('Type "REAL"')
        self.real_ack = QCheckBox("I understand real capital risk")
        btn = QPushButton("Enable REAL Trading")
        btn.clicked.connect(self._confirm_real)
        l.addWidget(self.real_text)
        l.addWidget(self.real_ack)
        l.addWidget(btn)
        return page

    def _confirm_real(self) -> None:
        if self.real_text.text() != "REAL" or not self.real_ack.isChecked():
            QMessageBox.warning(self, "Blocked", "Confirmation gate failed")
            return
        QMessageBox.information(self, "Countdown", "REAL mode armed in 10 seconds")


def launch_ui(config: AppConfig) -> None:
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(DARK_QSS)
    w = MainWindow(config)
    w.show()
    app.exec()
