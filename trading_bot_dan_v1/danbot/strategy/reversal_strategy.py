from __future__ import annotations

from dataclasses import dataclass

from danbot.core.config import StrategyConfig
from danbot.strategy.impulse_detector import detect_impulse
from danbot.strategy.signals import StrategySignal
from danbot.strategy.state_machine import ImpulseLifecycleMachine, MarketState


@dataclass
class ReversalStrategy:
    config: StrategyConfig

    def __post_init__(self) -> None:
        self.machine_by_symbol: dict[str, ImpulseLifecycleMachine] = {}

    def evaluate(self, symbol: str, features: dict[str, float], imbalance_factor: float, structure_confirmed: bool) -> StrategySignal:
        machine = self.machine_by_symbol.setdefault(symbol, ImpulseLifecycleMachine())
        impulse = detect_impulse(
            price_change_pct=features.get("return_pct", 0.0),
            seconds=60,
            volume_z=features.get("volume_zscore", 0.0),
            imbalance_factor=imbalance_factor,
            threshold_pct=self.config.impulse_threshold_pct,
        )
        exhaustion = (
            features.get("exhaustion_ratio", 1.0) < self.config.exhaustion_ratio_threshold
            and features.get("wick_ratio", 0.0) > 1.2
        )
        climax = impulse.detected and abs(features.get("return_pct", 0.0)) > self.config.impulse_threshold_pct * 1.2
        rebalance = abs(features.get("return_pct", 0.0)) < 0.5
        state = machine.transition(impulse.detected, climax, exhaustion, rebalance)

        reasons: list[str] = []
        side = None
        confidence = min(1.0, max(0.0, impulse.score))
        if state == MarketState.EXHAUSTION and structure_confirmed:
            side = "SELL" if features.get("return_pct", 0) > 0 else "BUY"
            reasons.extend(["exhaustion", "first_structure_confirmed"])
            confidence = min(1.0, confidence + 0.2)
        return StrategySignal(symbol=symbol, state=state, confidence=confidence, side=side, reason_codes=reasons, features=features)
