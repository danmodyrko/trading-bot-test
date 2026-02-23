from __future__ import annotations

PRIMARY_BG = "#0B1220"
GLASS = "rgba(255,255,255,0.06)"
GLASS_STRONG = "rgba(255,255,255,0.10)"
BORDER = "rgba(255,255,255,0.12)"
TEXT_MAIN = "#E6EDF7"
TEXT_MUTED = "rgba(230,237,247,0.65)"
ACCENT_GREEN = "#39D98A"
ACCENT_RED = "#FF5A5F"
ACCENT_GOLD = "#F6C453"
ACCENT_BLUE = "#5AA9FF"

CARD_RADIUS = 22
PILL_RADIUS = 18
BTN_RADIUS = 14

OUTER_PADDING = 20
GAP = 16
INNER_PADDING = 18

FONT_STACK = "Inter, 'Segoe UI'"

DARK_QSS = f"""

QPushButton {{
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.12);
    background: rgba(18,29,45,0.82);
    color: #E6EDF7;
    padding: 10px 16px;
    font-weight: 700;
}}
QPushButton:hover {{
    border: 1px solid rgba(108,195,255,0.95);
    background: rgba(39,62,92,0.92);
}}
QPushButton:pressed, QPushButton[flashPressed="true"] {{
    border: 1px solid rgba(78,142,196,0.95);
    background: rgba(20,32,48,0.95);
    padding-top: 11px;
    padding-bottom: 9px;
}}
QPushButton:disabled {{
    color: rgba(230,237,247,0.45);
    border: 1px solid rgba(255,255,255,0.08);
    background: rgba(18,29,45,0.45);
}}
QPushButton[variant="primary"] {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #47E698, stop:1 #2ABF72);
    color: #07170f;
    border: 1px solid rgba(111,255,189,0.55);
}}
QPushButton[variant="danger"] {{
    background: rgba(24,13,15,0.88);
    color: #ffd8da;
    border: 1px solid rgba(255,90,95,0.55);
}}
QWidget {{
    background-color: {PRIMARY_BG};
    color: {TEXT_MAIN};
    font-family: {FONT_STACK};
    font-size: 14px;
}}
QLineEdit, QComboBox {{
    background: rgba(255,255,255,0.07);
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 8px 10px;
    color: {TEXT_MAIN};
}}
QLineEdit:focus, QComboBox:focus {{
    border: 1px solid rgba(90,169,255,0.85);
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: rgba(255,255,255,0.24);
    border-radius: 5px;
    min-height: 30px;
}}
"""
