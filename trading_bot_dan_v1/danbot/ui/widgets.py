from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class SymbolCard(QFrame):
    def __init__(self, symbol: str) -> None:
        super().__init__()
        self.setObjectName("symbol_card")
        layout = QVBoxLayout(self)
        self.symbol_label = QLabel(symbol)
        self.price_label = QLabel("0.0")
        self.state_label = QLabel("BUILDUP")
        self.conf_label = QLabel("0%")
        layout.addWidget(self.symbol_label)
        layout.addWidget(self.price_label)
        layout.addWidget(self.state_label)
        layout.addWidget(self.conf_label)

    def update_data(self, price: float, state: str, confidence: float) -> None:
        self.price_label.setText(f"{price:.4f}")
        self.state_label.setText(state)
        self.conf_label.setText(f"{confidence*100:.0f}%")
