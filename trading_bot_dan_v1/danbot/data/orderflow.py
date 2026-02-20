from __future__ import annotations

from collections import deque


class OrderflowTracker:
    def __init__(self, maxlen: int = 200) -> None:
        self.buy_qty = deque(maxlen=maxlen)
        self.sell_qty = deque(maxlen=maxlen)

    def add_trade(self, qty: float, is_buyer_maker: bool) -> None:
        if is_buyer_maker:
            self.sell_qty.append(qty)
            self.buy_qty.append(0.0)
        else:
            self.buy_qty.append(qty)
            self.sell_qty.append(0.0)

    @property
    def imbalance_factor(self) -> float:
        buy = sum(self.buy_qty)
        sell = sum(self.sell_qty)
        total = max(buy + sell, 1e-9)
        return abs(buy - sell) / total
