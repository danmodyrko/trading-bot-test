from __future__ import annotations

from dataclasses import dataclass

from danbot.exchange.models import OrderRequest, Side


@dataclass
class SlippageModel:
    max_slippage_bps: float
    spread_guard_bps: float
    edge_safety_factor: float

    def expected_slippage_bps(self, order_size: float, spread_bps: float, volatility: float, depth: float | None, impact: float) -> float:
        if depth and depth > 0:
            depth_component = (order_size / depth) * 10_000
            return spread_bps * 0.5 + depth_component + volatility * 10_000 * 0.15
        return spread_bps * 0.5 + impact * order_size * 10_000 + volatility * 10_000 * 0.15

    def validate(self, expected_bps: float, spread_bps: float, expected_edge_bps: float) -> tuple[bool, str]:
        if spread_bps > self.spread_guard_bps:
            return False, "spread_guard"
        if expected_bps > self.max_slippage_bps:
            return False, "slippage_guard"
        if expected_bps > expected_edge_bps * self.edge_safety_factor:
            return False, "cost_exceeds_edge"
        return True, "ok"


def make_reduce_only_exit(symbol: str, side: Side, qty: float) -> OrderRequest:
    closing_side = Side.SELL if side == Side.BUY else Side.BUY
    return OrderRequest(symbol=symbol, side=closing_side, qty=qty, reduce_only=True)
