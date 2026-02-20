from __future__ import annotations

from dataclasses import dataclass, field

from danbot.strategy.state_machine import MarketState


@dataclass
class StrategySignal:
    symbol: str
    state: MarketState
    confidence: float
    side: str | None = None
    reason_codes: list[str] = field(default_factory=list)
    features: dict[str, float] = field(default_factory=dict)
