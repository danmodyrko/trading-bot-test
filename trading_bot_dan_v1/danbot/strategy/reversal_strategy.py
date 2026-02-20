from __future__ import annotations

from dataclasses import dataclass

from danbot.core.config import StrategyConfig
from danbot.strategy.signals import StrategySignal
from danbot.strategy.state_machine import MarketState, ProbabilisticStateMachine


@dataclass
class ReversalStrategy:
    config: StrategyConfig

    def __post_init__(self) -> None:
        self.machine_by_symbol: dict[str, ProbabilisticStateMachine] = {}

    def evaluate(self, symbol: str, features: dict[str, float], structure_confirmed: bool, regime_ok: bool = True) -> StrategySignal:
        machine = self.machine_by_symbol.setdefault(symbol, ProbabilisticStateMachine())
        conf = machine.update(
            impulse_score=features.get("impulse_score", 0.0),
            impulse_detected=bool(features.get("impulse_detected", False)),
            exhaustion_detected=bool(features.get("exhaustion_detected", False)),
            exhaustion_ratio=features.get("exhaustion_ratio", 1.0),
            wick_proxy=features.get("wick_proxy", 0.0),
            structure_confirmed=structure_confirmed,
        )
        state = machine.current_state
        reasons: list[str] = []
        side = None
        impulse_falling = conf[MarketState.IMPULSE] < 0.35
        if not regime_ok:
            reasons.append("regime_filter_block")
        if conf[MarketState.EXHAUSTION] > self.config.exhaustion_confidence_threshold and impulse_falling and structure_confirmed and regime_ok:
            side = "SELL" if features.get("price_change_pct", 0) > 0 else "BUY"
            reasons.extend(["exhaustion_confident", "impulse_falling", "structure_confirmed"])
        elif conf[MarketState.EXHAUSTION] <= self.config.exhaustion_confidence_threshold:
            reasons.append("exhaustion_low_confidence")
        return StrategySignal(
            symbol=symbol,
            state=state,
            confidence=conf[state],
            side=side,
            reason_codes=reasons,
            features={**features, **{f"conf_{s.value}": v for s, v in conf.items()}},
        )
