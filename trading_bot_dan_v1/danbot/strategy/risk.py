from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class RiskManager:
    max_daily_loss_pct: float
    max_positions: int
    max_trade_risk_pct: float
    max_notional_per_trade: float
    cooldown_seconds: int
    max_positions_per_symbol: int = 1
    max_exposure_per_symbol: float = 500.0
    max_account_exposure: float = 2_000.0
    max_consecutive_losses: int = 4
    loss_cooldown_seconds: int = 90
    include_unrealized_pnl: bool = True
    loss_today_pct: float = 0.0
    open_positions: int = 0
    kill_switch: bool = False
    vol_blocked_until: datetime | None = None
    consecutive_losses: int = 0
    open_positions_by_symbol: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    exposure_by_symbol: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    _cooldown_until: dict[str, datetime] = field(default_factory=dict)
    _reasons: deque[str] = field(default_factory=lambda: deque(maxlen=100))

    def can_trade(
        self,
        symbol: str,
        notional: float,
        stale: bool = False,
        spread_blocked: bool = False,
        slippage_blocked: bool = False,
    ) -> tuple[bool, str]:
        now = datetime.now(timezone.utc)
        if self.kill_switch:
            return self._deny("kill_switch")
        if stale:
            return self._deny("staleness_block")
        if spread_blocked:
            return self._deny("spread_block")
        if slippage_blocked:
            return self._deny("slippage_block")
        if self.vol_blocked_until and now < self.vol_blocked_until:
            return self._deny("volatility_block")
        if self.loss_today_pct >= self.max_daily_loss_pct:
            return self._deny("daily_loss_circuit_breaker")
        if self.consecutive_losses >= self.max_consecutive_losses:
            return self._deny("consecutive_losses_circuit_breaker")
        if self.open_positions >= self.max_positions:
            return self._deny("max_positions")
        if self.open_positions_by_symbol[symbol] >= self.max_positions_per_symbol:
            return self._deny("max_positions_per_symbol")
        symbol_exposure = self.exposure_by_symbol[symbol] + notional
        if symbol_exposure > self.max_exposure_per_symbol:
            return self._deny("max_symbol_exposure")
        total_exposure = sum(self.exposure_by_symbol.values()) + notional
        if total_exposure > self.max_account_exposure:
            return self._deny("max_account_exposure")
        cooldown = self._cooldown_until.get(symbol)
        if cooldown and now < cooldown:
            return self._deny("symbol_cooldown")
        return True, "ok"

    def apply_trade_open(self, symbol: str, notional: float) -> None:
        self.open_positions += 1
        self.open_positions_by_symbol[symbol] += 1
        self.exposure_by_symbol[symbol] += max(notional, 0.0)
        self._cooldown_until[symbol] = datetime.now(timezone.utc) + timedelta(seconds=self.cooldown_seconds)

    def apply_trade_close(self, symbol: str, pnl_pct: float, released_notional: float) -> None:
        self.open_positions = max(0, self.open_positions - 1)
        self.open_positions_by_symbol[symbol] = max(0, self.open_positions_by_symbol[symbol] - 1)
        self.exposure_by_symbol[symbol] = max(0.0, self.exposure_by_symbol[symbol] - max(released_notional, 0.0))
        if pnl_pct < 0:
            self.consecutive_losses += 1
            self._cooldown_until[symbol] = datetime.now(timezone.utc) + timedelta(seconds=self.loss_cooldown_seconds)
        else:
            self.consecutive_losses = 0

    def update_pnl(self, realized_pct: float, unrealized_pct: float = 0.0) -> None:
        self.loss_today_pct = max(realized_pct + (unrealized_pct if self.include_unrealized_pnl else 0.0), 0.0)

    def update_volatility(self, vol_10s: float, threshold: float, cooldown_seconds: int) -> bool:
        if vol_10s > threshold:
            self.vol_blocked_until = datetime.now(timezone.utc) + timedelta(seconds=cooldown_seconds)
            return True
        return False

    def engage_kill_switch(self) -> None:
        self.kill_switch = True

    def release_kill_switch(self) -> None:
        self.kill_switch = False

    def snapshot(self) -> dict[str, object]:
        return {
            "loss_today_pct": self.loss_today_pct,
            "open_positions": self.open_positions,
            "open_positions_by_symbol": dict(self.open_positions_by_symbol),
            "exposure_by_symbol": dict(self.exposure_by_symbol),
            "cooldown_until": {k: v.isoformat() for k, v in self._cooldown_until.items()},
            "consecutive_losses": self.consecutive_losses,
            "kill_switch": self.kill_switch,
        }

    def _deny(self, reason: str) -> tuple[bool, str]:
        self._reasons.append(reason)
        return False, reason

    def position_size(self, equity: float, confidence: float, stop_distance_pct: float, size_multiplier: float = 1.0) -> float:
        risk_budget = equity * (self.max_trade_risk_pct / 100) * max(min(confidence, 1.0), 0.1)
        size = risk_budget / max(stop_distance_pct / 100, 1e-6)
        return min(size * max(0.2, min(size_multiplier, 1.5)), self.max_notional_per_trade)
