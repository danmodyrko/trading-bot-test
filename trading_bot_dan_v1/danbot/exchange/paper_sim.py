from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from danbot.exchange.models import Fill, OrderRequest, Position, Side


@dataclass
class PaperSimulator:
    equity: float = 10_000.0
    fee_bps: float = 4.0
    slippage_bps: float = 2.0
    positions: dict[str, Position] = field(default_factory=dict)

    def _apply_slippage(self, price: float, side: Side) -> float:
        bump = price * (self.slippage_bps / 10_000)
        return price + bump if side == Side.BUY else price - bump

    def place_order(self, order: OrderRequest, mark_price: float) -> Fill:
        fill_price = self._apply_slippage(mark_price, order.side)
        fee = abs(order.qty * fill_price) * self.fee_bps / 10_000
        fill = Fill(
            symbol=order.symbol,
            side=order.side,
            qty=order.qty,
            price=fill_price,
            fee=fee,
            ts=datetime.now(timezone.utc),
            order_id=str(uuid.uuid4()),
        )
        pos = self.positions.setdefault(order.symbol, Position(symbol=order.symbol))
        signed_qty = order.qty if order.side == Side.BUY else -order.qty
        new_qty = pos.qty + signed_qty
        if pos.qty == 0:
            pos.entry_price = fill_price
        elif new_qty != 0:
            pos.entry_price = ((pos.qty * pos.entry_price) + (signed_qty * fill_price)) / new_qty
        pos.qty = new_qty
        pos.updated_at = fill.ts
        self.equity -= fee
        return fill
