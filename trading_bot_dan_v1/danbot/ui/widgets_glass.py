from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QKeySequence, QPainter, QPainterPath, QPen, QPixmap, QShortcut
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QDoubleSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QDialog,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from danbot.ui.theme import ACCENT_BLUE, ACCENT_GOLD, ACCENT_GREEN, ACCENT_RED, BORDER, BTN_RADIUS, CARD_RADIUS, GLASS, GLASS_STRONG, INNER_PADDING, PILL_RADIUS, TEXT_MAIN, TEXT_MUTED
from danbot.ui.viewmodels import LiveLogEntry

_ICON_CACHE: dict[tuple[str, int], QPixmap] = {}
_ICON_DIR = Path(__file__).parent / "assets" / "icons"


def svg_pixmap(name: str, size: int = 16, color: str | None = None) -> QPixmap:
    key = (f"{name}:{color or ''}", size)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    renderer = QSvgRenderer(str(_ICON_DIR / name))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    if color:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(color))
    painter.end()
    _ICON_CACHE[key] = pixmap
    return pixmap


class GlassCard(QWidget):
    def __init__(self, title: str = "") -> None:
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(INNER_PADDING, INNER_PADDING, INNER_PADDING, INNER_PADDING)
        self.layout.setSpacing(10)
        if title:
            self.title_label = QLabel(title)
            self.title_label.setStyleSheet(f"font-size: 18px; font-weight: 600; color: {TEXT_MAIN};")
            self.layout.addWidget(self.title_label)

    def set_content(self, widget: QWidget) -> None:
        self.layout.addWidget(widget)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, CARD_RADIUS, CARD_RADIUS)
        painter.fillPath(path, QColor(GLASS))
        painter.setPen(QPen(QColor(BORDER), 1.0))
        painter.drawPath(path)


class PillBadge(QWidget):
    def __init__(self, icon: str, text: str, tint: str) -> None:
        super().__init__()
        l = QHBoxLayout(self)
        l.setContentsMargins(12, 7, 12, 7)
        l.setSpacing(8)
        self.icon_lbl = QLabel()
        self.icon_lbl.setPixmap(svg_pixmap(icon, 14, tint))
        self.text_lbl = QLabel(text)
        self.text_lbl.setStyleSheet(f"font-weight: 600; color: {TEXT_MAIN};")
        self.setStyleSheet(f"background: {GLASS_STRONG}; border: 1px solid {BORDER}; border-radius: {PILL_RADIUS}px;")
        l.addWidget(self.icon_lbl)
        l.addWidget(self.text_lbl)


class GlassButton(QPushButton):
    def __init__(self, text: str, variant: str = "secondary") -> None:
        super().__init__(text)
        if variant == "primary":
            style = "background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #47E698, stop:1 #2ABF72); color: #07170f;"
        elif variant == "danger":
            style = "background: rgba(24,13,15,0.85); color: #ffd8da; border: 1px solid rgba(255,90,95,0.45);"
        else:
            style = f"background: {GLASS_STRONG}; color: {TEXT_MAIN};"
        self.setStyleSheet(f"QPushButton {{ {style} border: 1px solid {BORDER}; border-radius: {BTN_RADIUS}px; padding: 10px 16px; font-weight: 700; }}")
        self.setMinimumHeight(40)


class LogRow(QFrame):
    def __init__(self, entry: LiveLogEntry) -> None:
        super().__init__()
        l = QHBoxLayout(self)
        l.setContentsMargins(10, 8, 10, 8)
        color_map = {"SIGNAL": ACCENT_BLUE, "EXECUTE": ACCENT_GREEN, "RISK": ACCENT_RED, "EXIT": ACCENT_GOLD, "INCIDENT": ACCENT_RED, "INFO": TEXT_MUTED}
        color = color_map.get(entry.category.upper(), ACCENT_BLUE)
        tag = QLabel(entry.category.upper())
        tag.setStyleSheet(f"color:{color};font-weight:700;")
        msg = QLabel(entry.message)
        ts = QLabel(entry.ts_iso[11:19])
        ts.setStyleSheet(f"color:{TEXT_MUTED};")
        l.addWidget(tag)
        l.addWidget(msg, 1)
        l.addWidget(ts)


class LiveLogPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Severity", "Message", "Time"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.cellDoubleClicked.connect(lambda *_: self.copy_selected())
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(1, self.table.horizontalHeader().ResizeMode.Stretch)
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(2, 130)
        QShortcut(QKeySequence.StandardKey.Copy, self.table, activated=self.copy_selected)
        root.addWidget(self.table, 1)

    def set_entries(self, entries: list[LiveLogEntry]) -> None:
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            severity = QTableWidgetItem(entry.severity.upper())
            message = QTableWidgetItem(entry.message)
            ts = QTableWidgetItem(entry.ts_iso[11:19])
            self.table.setItem(row, 0, severity)
            self.table.setItem(row, 1, message)
            self.table.setItem(row, 2, ts)
        if entries:
            self.table.scrollToBottom()

    def copy_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        severity = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
        message = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
        ts = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
        QGuiApplication.clipboard().setText(f"[{ts}] {severity}: {message}")

    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        action = menu.addAction("Copy")
        action.triggered.connect(self.copy_selected)
        menu.exec(self.table.viewport().mapToGlobal(pos))


class MetricCard(QWidget):
    def __init__(self, title: str, value: str, accent: str) -> None:
        super().__init__()
        l = QVBoxLayout(self)
        l.setContentsMargins(12, 10, 12, 10)
        self.title = QLabel(title)
        self.title.setStyleSheet(f"color:{TEXT_MUTED};font-weight:600;")
        self.value = QLabel(value)
        self.value.setStyleSheet(f"font-size:26px;font-weight:700;color:{accent};")
        l.addWidget(self.title)
        l.addWidget(self.value)

    def set_value(self, value: str) -> None:
        self.value.setText(value)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 16, 16)
        painter.fillPath(path, QColor(GLASS))
        painter.setPen(QPen(QColor(BORDER), 1.0))
        painter.drawPath(path)


class SettingsPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        self.form_root = QVBoxLayout(host)
        self.form_root.setSpacing(12)
        self._build_mode()
        self._build_presets()
        self._build_keys()
        self._build_risk()
        self._build_strategy()
        self._build_ml()
        actions = QHBoxLayout()
        self.save_btn = GlassButton("Save", "primary")
        self.apply_btn = GlassButton("Apply (no restart)")
        actions.addStretch()
        actions.addWidget(self.save_btn)
        actions.addWidget(self.apply_btn)
        self.form_root.addLayout(actions)
        self.connection_status = QLabel("Connection test status: idle")
        self.connection_status.setStyleSheet(f"color: {TEXT_MUTED};")
        self.form_root.addWidget(self.connection_status)
        scroll.setWidget(host)
        root.addWidget(scroll)

    def set_connection_status(self, text: str, is_error: bool = False) -> None:
        color = ACCENT_RED if is_error else ACCENT_GREEN
        self.connection_status.setStyleSheet(f"color: {color}; font-weight: 600;")
        self.connection_status.setText(text)

    def _build_mode(self) -> None:
        group = QGroupBox("Mode & Safety")
        form = QFormLayout(group)
        self.mode_combo = QComboBox(); self.mode_combo.addItems(["DEMO", "REAL"])
        self.dry_run = QCheckBox("DRY RUN")
        self.real_gate = QLineEdit(); self.real_gate.setPlaceholderText("Type REAL to unlock")
        self.real_confirm = QCheckBox("I understand REAL mode risk")
        self.kill_status = QLabel("OFF")
        form.addRow("Mode", self.mode_combo)
        form.addRow("", self.dry_run)
        form.addRow("REAL gate", self.real_gate)
        form.addRow("", self.real_confirm)
        form.addRow("Kill switch", self.kill_status)
        self.form_root.addWidget(group)

    def _build_presets(self) -> None:
        group = QGroupBox("Risk Presets")
        root = QVBoxLayout(group)
        root.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.preset_group = QButtonGroup(self)
        self.preset_buttons: dict[str, QPushButton] = {}
        presets = [
            ("SAFE", "0.5% | 3x | 1 pos"),
            ("MEDIUM", "1% | 5x | 2 pos"),
            ("AGGRESSIVE", "2% | 8x | 3 pos"),
            ("INSANE", "4% | 15x | 5 pos"),
        ]
        for name, headline in presets:
            btn = QPushButton(f"{name}\n{headline}")
            btn.setCheckable(True)
            btn.setMinimumHeight(52)
            btn.setStyleSheet(
                "QPushButton {"
                f"background: {GLASS_STRONG}; color: {TEXT_MAIN}; border: 1px solid {BORDER};"
                "border-radius: 12px; padding: 6px 10px; font-weight: 700; text-align: left;"
                "}"
                "QPushButton:checked {border: 1px solid #4CE6A0; background: rgba(71,230,152,0.18);}"
            )
            self.preset_buttons[name] = btn
            self.preset_group.addButton(btn)
            row.addWidget(btn)
        self.custom_indicator = QLabel("CUSTOM")
        self.custom_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.custom_indicator.setMinimumHeight(52)
        self.custom_indicator.setStyleSheet(
            f"background: {GLASS_STRONG}; color: {TEXT_MUTED}; border: 1px solid {BORDER}; border-radius: 12px; font-weight: 700;"
        )
        row.addWidget(self.custom_indicator)
        root.addLayout(row)
        self.active_profile_label = QLabel("Active profile: CUSTOM")
        self.active_profile_label.setStyleSheet(f"color: {TEXT_MUTED}; font-weight: 600;")
        root.addWidget(self.active_profile_label)
        self.form_root.addWidget(group)

    def set_active_profile(self, profile: str) -> None:
        for name, btn in self.preset_buttons.items():
            btn.setChecked(name == profile)
        is_custom = profile == "CUSTOM"
        if is_custom:
            self.custom_indicator.setStyleSheet(
                "background: rgba(255,190,92,0.18); color: #ffd99b; border: 1px solid rgba(255,190,92,0.5); border-radius: 12px; font-weight: 700;"
            )
        else:
            self.custom_indicator.setStyleSheet(
                f"background: {GLASS_STRONG}; color: {TEXT_MUTED}; border: 1px solid {BORDER}; border-radius: 12px; font-weight: 700;"
            )
        self.active_profile_label.setText(f"Active profile: {profile}")

    def _build_keys(self) -> None:
        group = QGroupBox("API Keys")
        grid = QGridLayout(group)
        self.demo_key = QLineEdit(); self.demo_secret = QLineEdit(); self.demo_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.real_key = QLineEdit(); self.real_secret = QLineEdit(); self.real_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.test_demo_btn = GlassButton("Test DEMO Connection")
        self.test_real_btn = GlassButton("Test REAL Connection")
        grid.addWidget(QLabel("Demo Key"), 0, 0); grid.addWidget(self.demo_key, 0, 1)
        grid.addWidget(QLabel("Demo Secret"), 1, 0); grid.addWidget(self.demo_secret, 1, 1)
        grid.addWidget(self.test_demo_btn, 2, 1)
        grid.addWidget(QLabel("Real Key"), 3, 0); grid.addWidget(self.real_key, 3, 1)
        grid.addWidget(QLabel("Real Secret"), 4, 0); grid.addWidget(self.real_secret, 4, 1)
        grid.addWidget(self.test_real_btn, 5, 1)
        self.form_root.addWidget(group)

    def _build_risk(self) -> None:
        group = QGroupBox("Trade / Risk Settings")
        form = QFormLayout(group)
        self.order_value = QDoubleSpinBox(); self.order_value.setDecimals(4); self.order_value.setSingleStep(0.001); self.order_value.setMaximum(1)
        self.max_lev = QSpinBox(); self.max_lev.setMaximum(125)
        self.max_pos = QSpinBox(); self.max_pos.setMaximum(100)
        self.max_loss = QDoubleSpinBox(); self.max_loss.setDecimals(4); self.max_loss.setMaximum(1)
        self.cooldown = QSpinBox(); self.cooldown.setMaximum(3600)
        self.spread = QDoubleSpinBox(); self.spread.setMaximum(1000)
        self.slippage = QDoubleSpinBox(); self.slippage.setMaximum(1000)
        self.edge_gate = QDoubleSpinBox(); self.edge_gate.setDecimals(2); self.edge_gate.setMaximum(10)
        self.vol_kill = QDoubleSpinBox(); self.vol_kill.setDecimals(4); self.vol_kill.setMaximum(10)
        self.regime = QCheckBox("Enable")
        self.regime_thr = QDoubleSpinBox(); self.regime_thr.setMaximum(10)
        self.max_tph = QSpinBox(); self.max_tph.setMaximum(1000)
        for lbl, w in [
            ("Order value (% balance)", self.order_value),
            ("Max Leverage", self.max_lev),
            ("Max positions", self.max_pos),
            ("Max daily loss pct", self.max_loss),
            ("Cooldown sec", self.cooldown),
            ("Spread guard bps", self.spread),
            ("Max slippage bps", self.slippage),
            ("Edge gate factor", self.edge_gate),
            ("Vol 10s threshold", self.vol_kill),
            ("Regime filter", self.regime),
            ("Trend strength threshold", self.regime_thr),
            ("Max trades/hour", self.max_tph),
        ]:
            form.addRow(lbl, w)
        self.form_root.addWidget(group)

    def _build_strategy(self) -> None:
        group = QGroupBox("Strategy Parameters")
        form = QFormLayout(group)
        self.impulse_pct = QDoubleSpinBox(); self.impulse_pct.setMaximum(100)
        self.impulse_window = QSpinBox(); self.impulse_window.setMaximum(3600)
        self.exhaustion = QDoubleSpinBox(); self.exhaustion.setMaximum(10)
        self.tp_profile = QLineEdit(); self.tp_profile.setPlaceholderText("0.30,0.50,0.60")
        self.time_stop = QSpinBox(); self.time_stop.setMaximum(7200)
        self.stop_model = QComboBox(); self.stop_model.addItems(["ATR", "fixed"])
        for lbl, w in [("impulse_threshold_pct", self.impulse_pct), ("impulse_window_seconds", self.impulse_window), ("exhaustion_ratio_threshold", self.exhaustion), ("tp_profile", self.tp_profile), ("time stop sec", self.time_stop), ("stop model", self.stop_model)]:
            form.addRow(lbl, w)
        self.form_root.addWidget(group)

    def _build_ml(self) -> None:
        group = QGroupBox("AI / ML")
        form = QFormLayout(group)
        self.spike_toggle = QCheckBox("Spike Classifier")
        self.ml_toggle = QCheckBox("ML Gate")
        self.ml_threshold = QDoubleSpinBox(); self.ml_threshold.setMaximum(1); self.ml_threshold.setSingleStep(0.05)
        self.model_path = QLineEdit()
        self.export_btn = GlassButton("Export dataset")
        self.train_btn = GlassButton("Train")
        self.last_wr = QLabel("Not installed")
        form.addRow("", self.spike_toggle)
        form.addRow("", self.ml_toggle)
        form.addRow("ML threshold", self.ml_threshold)
        form.addRow("Model path", self.model_path)
        form.addRow("", self.export_btn)
        form.addRow("", self.train_btn)
        form.addRow("Last model winrate", self.last_wr)
        self.form_root.addWidget(group)


class SettingsWindow(QDialog):
    def __init__(self, settings_panel: SettingsPanel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Dan v1 Settings")
        self.setMinimumSize(960, 700)
        layout = QVBoxLayout(self)
        layout.addWidget(settings_panel)
        controls = QHBoxLayout()
        controls.addStretch()
        self.close_btn = GlassButton("Close")
        controls.addWidget(self.close_btn)
        layout.addLayout(controls)
