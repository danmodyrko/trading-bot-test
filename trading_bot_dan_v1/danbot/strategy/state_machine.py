from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MarketState(str, Enum):
    BUILDUP = "BUILDUP"
    IMPULSE = "IMPULSE"
    CLIMAX = "CLIMAX"
    EXHAUSTION = "EXHAUSTION"
    REBALANCE = "REBALANCE"


@dataclass
class ProbabilisticStateMachine:
    ema_alpha: float = 0.25
    confidences: dict[MarketState, float] = field(
        default_factory=lambda: {state: (1.0 if state == MarketState.BUILDUP else 0.0) for state in MarketState}
    )

    def update(
        self,
        impulse_score: float,
        impulse_detected: bool,
        exhaustion_detected: bool,
        exhaustion_ratio: float,
        wick_proxy: float,
        structure_confirmed: bool,
    ) -> dict[MarketState, float]:
        raw = {
            MarketState.BUILDUP: max(0.0, 1.0 - impulse_score),
            MarketState.IMPULSE: min(1.0, impulse_score + (0.2 if impulse_detected else 0.0)),
            MarketState.CLIMAX: min(1.0, impulse_score * 0.8 + wick_proxy * 50),
            MarketState.EXHAUSTION: min(1.0, (1.0 - exhaustion_ratio) * 0.8 + (0.2 if exhaustion_detected else 0.0)),
            MarketState.REBALANCE: 0.6 if structure_confirmed else 0.2,
        }
        total = sum(raw.values()) or 1.0
        for state, value in raw.items():
            normalized = value / total
            self.confidences[state] = (1 - self.ema_alpha) * self.confidences[state] + self.ema_alpha * normalized
        return self.confidences.copy()

    @property
    def current_state(self) -> MarketState:
        return max(self.confidences.items(), key=lambda kv: kv[1])[0]
