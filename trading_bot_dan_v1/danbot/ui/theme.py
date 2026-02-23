from __future__ import annotations

PRIMARY_BG = "#F6F7F9"
GLASS = "#FFFFFF"
GLASS_STRONG = "#FFFFFF"
BORDER = "#E2E6EC"
TEXT_MAIN = "#111827"
TEXT_MUTED = "#6B7280"
ACCENT_GREEN = "#1F9D62"
ACCENT_RED = "#D14343"
ACCENT_GOLD = "#B7791F"
ACCENT_BLUE = "#1A73E8"

CARD_RADIUS = 14
PILL_RADIUS = 12
BTN_RADIUS = 10

OUTER_PADDING = 20
GAP = 14
INNER_PADDING = 16

FONT_STACK = "'Segoe UI', Inter, Arial"

DARK_QSS = f"""
QWidget {{
    background-color: {PRIMARY_BG};
    color: {TEXT_MAIN};
    font-family: {FONT_STACK};
    font-size: 13px;
}}
QPushButton {{
    border-radius: {BTN_RADIUS}px;
    border: 1px solid {BORDER};
    background: #FFFFFF;
    color: {TEXT_MAIN};
    padding: 9px 14px;
    font-weight: 600;
}}
QPushButton:hover {{
    border: 1px solid #CBD5E1;
    background: #F8FAFC;
}}
QPushButton:pressed, QPushButton[flashPressed="true"] {{
    background: #EEF2FF;
    border: 1px solid #AFC8F5;
}}
QPushButton:disabled {{
    color: #9CA3AF;
    background: #F3F4F6;
}}
QPushButton[variant="primary"] {{
    background: {ACCENT_BLUE};
    color: #FFFFFF;
    border: 1px solid #1669D6;
}}
QPushButton[variant="danger"] {{
    background: #FFF1F1;
    color: {ACCENT_RED};
    border: 1px solid #F3C8C8;
}}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {{
    background: #FFFFFF;
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 7px 9px;
    color: {TEXT_MAIN};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {{
    border: 1px solid {ACCENT_BLUE};
}}
QGroupBox {{
    background: #FFFFFF;
    border: 1px solid {BORDER};
    border-radius: {CARD_RADIUS}px;
    margin-top: 8px;
    padding-top: 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
"""
