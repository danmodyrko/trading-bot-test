from __future__ import annotations

from dataclasses import dataclass

from danbot.exchange.models import OrderRequest, Side


@dataclass
class ExecutionGuard:
    max_slippage_bps: float
    spread_guard_bps: float
    min_depth: float

    def validate(self, expected_bps: float, spread_bps: float, depth: float) -> tuple[bool, str]:
        if expected_bps > self.max_slippage_bps:
            return False, "slippage_guard"
        if spread_bps > self.spread_guard_bps:
            return False, "spread_guard"
        if depth < self.min_depth:
            return False, "depth_guard"
        return True, "ok"


def make_reduce_only_exit(symbol: str, side: Side, qty: float) -> OrderRequest:
    closing_side = Side.SELL if side == Side.BUY else Side.BUY
    return OrderRequest(symbol=symbol, side=closing_side, qty=qty, reduce_only=True)
