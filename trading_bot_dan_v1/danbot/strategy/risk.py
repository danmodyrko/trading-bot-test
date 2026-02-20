from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class RiskManager:
    max_daily_loss_pct: float
    max_positions: int
    max_trade_risk_pct: float
    max_notional_per_trade: float
    cooldown_seconds: int
    loss_today_pct: float = 0.0
    open_positions: int = 0
    kill_switch: bool = False
    vol_blocked_until: datetime | None = None

    def can_trade(self, stale: bool = False, spread_blocked: bool = False, slippage_blocked: bool = False) -> tuple[bool, str]:
        now = datetime.now(timezone.utc)
        if self.kill_switch:
            return False, "kill_switch"
        if stale:
            return False, "staleness_block"
        if spread_blocked:
            return False, "spread_block"
        if slippage_blocked:
            return False, "slippage_block"
        if self.vol_blocked_until and now < self.vol_blocked_until:
            return False, "volatility_block"
        if self.loss_today_pct >= self.max_daily_loss_pct:
            return False, "daily_loss_circuit_breaker"
        if self.open_positions >= self.max_positions:
            return False, "max_positions"
        return True, "ok"

    def update_volatility(self, vol_10s: float, threshold: float, cooldown_seconds: int) -> bool:
        if vol_10s > threshold:
            self.vol_blocked_until = datetime.now(timezone.utc) + timedelta(seconds=cooldown_seconds)
            return True
        return False

    def position_size(self, equity: float, confidence: float, stop_distance_pct: float, size_multiplier: float = 1.0) -> float:
        risk_budget = equity * (self.max_trade_risk_pct / 100) * max(min(confidence, 1.0), 0.1)
        size = risk_budget / max(stop_distance_pct / 100, 1e-6)
        return min(size * max(0.2, min(size_multiplier, 1.5)), self.max_notional_per_trade)
