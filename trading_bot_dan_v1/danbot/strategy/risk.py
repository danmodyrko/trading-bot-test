from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskManager:
    max_daily_loss_pct: float
    max_positions: int
    max_trade_risk_pct: float
    max_notional_per_trade: float
    cooldown_seconds: int
    loss_today_pct: float = 0.0
    open_positions: int = 0

    def can_trade(self) -> tuple[bool, str]:
        if self.loss_today_pct >= self.max_daily_loss_pct:
            return False, "daily_loss_circuit_breaker"
        if self.open_positions >= self.max_positions:
            return False, "max_positions"
        return True, "ok"

    def position_size(self, equity: float, confidence: float, stop_distance_pct: float) -> float:
        risk_budget = equity * (self.max_trade_risk_pct / 100) * max(min(confidence, 1.0), 0.1)
        size = risk_budget / max(stop_distance_pct / 100, 1e-6)
        return min(size, self.max_notional_per_trade)
