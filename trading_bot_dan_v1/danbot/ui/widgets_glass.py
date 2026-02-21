from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from danbot.ui.theme import (
    ACCENT_BLUE,
    ACCENT_GOLD,
    ACCENT_GREEN,
    ACCENT_RED,
    BORDER,
    BTN_RADIUS,
    CARD_RADIUS,
    GLASS,
    GLASS_STRONG,
    INNER_PADDING,
    PILL_RADIUS,
    TEXT_MAIN,
    TEXT_MUTED,
)
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
    def __init__(self, title: str = "", controls: QWidget | None = None, accent: str | None = None) -> None:
        super().__init__()
        self.accent = accent
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(INNER_PADDING, INNER_PADDING, INNER_PADDING, INNER_PADDING)
        self.layout.setSpacing(12)

        self.header = QHBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"font-size: 18px; font-weight: 600; color: {TEXT_MAIN}; background: transparent;")
        self.header.addWidget(self.title_label)
        self.header.addStretch()
        if controls:
            self.header.addWidget(controls)
        self.layout.addLayout(self.header)

    def set_content(self, widget: QWidget) -> None:
        self.layout.addWidget(widget)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)

        path = QPainterPath()
        path.addRoundedRect(rect, CARD_RADIUS, CARD_RADIUS)

        grad_top = QColor(255, 255, 255, 30)
        grad_bottom = QColor(255, 255, 255, 10)
        painter.fillPath(path, QColor(GLASS))

        painter.setPen(QPen(QColor(BORDER), 1.0))
        painter.drawPath(path)

        highlight = rect.adjusted(4, 2, -4, -rect.height() + 16)
        painter.setPen(QPen(QColor(grad_top), 1.2))
        painter.drawRoundedRect(highlight, CARD_RADIUS - 6, CARD_RADIUS - 6)

        if self.accent:
            painter.setPen(Qt.PenStyle.NoPen)
            glow = rect.adjusted(20, 6, -20, -rect.height() + 20)
            painter.setBrush(QColor(self.accent + "55"))
            painter.drawRoundedRect(glow, 10, 10)


class PillBadge(QWidget):
    def __init__(self, icon: str, text: str, tint: str) -> None:
        super().__init__()
        l = QHBoxLayout(self)
        l.setContentsMargins(12, 7, 12, 7)
        l.setSpacing(8)
        self.setStyleSheet(
            f"background: {GLASS_STRONG}; border: 1px solid {BORDER}; border-radius: {PILL_RADIUS}px;"
        )
        icon_lbl = QLabel()
        icon_lbl.setPixmap(svg_pixmap(icon, 14, tint))
        txt = QLabel(text)
        txt.setStyleSheet(f"font-weight: 600; color: {TEXT_MAIN}; background: transparent;")
        l.addWidget(icon_lbl)
        l.addWidget(txt)


class GlassButton(QPushButton):
    def __init__(self, text: str, variant: str = "secondary") -> None:
        super().__init__(text)
        self.variant = variant
        self.setMinimumHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if variant == "primary":
            style = f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #47E698, stop:1 #2ABF72); color: #07170f;"
        elif variant == "danger":
            style = "background: rgba(24,13,15,0.85); color: #ffd8da; border: 1px solid rgba(255,90,95,0.45);"
        else:
            style = f"background: {GLASS_STRONG}; color: {TEXT_MAIN};"
        self.setStyleSheet(
            f"QPushButton {{ {style} border: 1px solid {BORDER}; border-radius: {BTN_RADIUS}px; padding: 10px 16px; font-weight: 700; }}"
            "QPushButton:disabled { opacity: 0.55; }"
        )


class StrategyPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(14)

        symbol_row = QHBoxLayout()
        coin = QLabel()
        coin.setPixmap(svg_pixmap("btc.svg", 20))
        self.symbol = QLabel("61464 BTC/USDT")
        self.symbol.setStyleSheet("font-size: 24px; font-weight: 700;")
        symbol_row.addWidget(coin)
        symbol_row.addWidget(self.symbol)
        symbol_row.addStretch()
        l.addLayout(symbol_row)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Impulse Score"))
        row1.addStretch()
        self.impulse_val = QLabel("0.00")
        self.impulse_val.setStyleSheet("font-weight: 600;")
        row1.addWidget(self.impulse_val)
        l.addLayout(row1)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setFixedHeight(8)
        self.progress.setStyleSheet(
            f"QProgressBar{{background: rgba(255,255,255,0.09); border:none; border-radius:4px;}}"
            f"QProgressBar::chunk{{background:{ACCENT_GREEN}; border-radius:4px;}}"
        )
        l.addWidget(self.progress)

        spread_row = QHBoxLayout()
        self.spread = QLabel("Spread 1.2 bps")
        spread_row.addWidget(self.spread)
        spread_row.addStretch()
        self.spread_value = QLabel("1.2")
        self.spread_value.setStyleSheet(f"color: {TEXT_MUTED};")
        spread_row.addWidget(self.spread_value)
        l.addLayout(spread_row)

        self.status = QLabel("Decay Detected")
        self.status.setStyleSheet(f"color:{TEXT_MUTED};")
        l.addWidget(self.status)
        l.addStretch()

        self.enter_button = GlassButton("ENTER LONG", "primary")
        self.enter_button.setEnabled(False)
        l.addWidget(self.enter_button)


class LogRow(QFrame):
    def __init__(self, entry: LiveLogEntry) -> None:
        super().__init__()
        self.setObjectName("logRow")
        self.setStyleSheet(
            f"QFrame#logRow{{background:transparent; border-radius:12px;}}"
            "QFrame#logRow:hover{background:rgba(255,255,255,0.06);}"
        )
        l = QHBoxLayout(self)
        l.setContentsMargins(10, 8, 10, 8)
        l.setSpacing(10)

        color_map = {
            "SIGNAL": ACCENT_BLUE,
            "EXECUTE": ACCENT_GREEN,
            "RISK": ACCENT_RED,
            "EXIT": ACCENT_GOLD,
            "INCIDENT": ACCENT_RED,
            "INFO": TEXT_MUTED,
        }
        icon_map = {
            "SIGNAL": "signal.svg",
            "EXECUTE": "execute.svg",
            "RISK": "risk_event.svg",
            "EXIT": "exit.svg",
            "INCIDENT": "incident.svg",
            "INFO": "signal.svg",
        }
        color = color_map.get(entry.category.upper(), ACCENT_BLUE)

        icon = QLabel()
        icon.setPixmap(svg_pixmap(icon_map.get(entry.category.upper(), "signal.svg"), 14, color))
        l.addWidget(icon)

        info = QVBoxLayout()
        top = QHBoxLayout()
        tag = QLabel(entry.category.upper())
        tag.setStyleSheet(f"color:{color}; font-weight:700;")
        top.addWidget(tag)
        if entry.symbol:
            sym = QLabel(entry.symbol)
            sym.setStyleSheet(f"color:{TEXT_MUTED};")
            top.addWidget(sym)
        top.addStretch()
        info.addLayout(top)

        msg = QLabel(entry.message)
        msg.setWordWrap(True)
        info.addWidget(msg)
        l.addLayout(info, 1)

        ts = QLabel(entry.ts_iso[11:19])
        ts.setStyleSheet(f"color:{TEXT_MUTED};")
        ts.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        l.addWidget(ts)


class LiveLogPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        control_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search")
        self.search.setFixedHeight(38)
        self.severity = QComboBox()
        self.severity.addItems(["ALL", "SIGNAL", "EXECUTE", "RISK", "EXIT", "INCIDENT", "INFO"])
        self.severity.setFixedHeight(38)
        control_row.addWidget(self.search, 1)
        control_row.addWidget(self.severity)
        root.addLayout(control_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.log_host = QWidget()
        self.log_layout = QVBoxLayout(self.log_host)
        self.log_layout.setContentsMargins(0, 0, 0, 0)
        self.log_layout.setSpacing(4)
        self.log_layout.addStretch()
        self.scroll.setWidget(self.log_host)
        root.addWidget(self.scroll, 1)

    def set_entries(self, entries: list[LiveLogEntry]) -> None:
        while self.log_layout.count() > 1:
            item = self.log_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for entry in entries[-250:]:
            self.log_layout.insertWidget(self.log_layout.count() - 1, LogRow(entry))


class MetricCard(QWidget):
    def __init__(self, title: str, value: str, accent: str, icon: str) -> None:
        super().__init__()
        self._accent = accent
        l = QVBoxLayout(self)
        l.setContentsMargins(16, 14, 16, 14)
        l.setSpacing(6)
        top = QHBoxLayout()
        ico = QLabel()
        ico.setPixmap(svg_pixmap(icon, 16, accent))
        top.addWidget(ico)
        t = QLabel(title)
        t.setStyleSheet(f"color:{TEXT_MUTED}; font-weight:600;")
        top.addWidget(t)
        top.addStretch()
        l.addLayout(top)
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"font-size: 30px; font-weight: 700; color:{accent};")
        l.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 18, 18)
        painter.fillPath(path, QColor(GLASS))
        painter.setPen(QPen(QColor(BORDER), 1.0))
        painter.drawPath(path)
