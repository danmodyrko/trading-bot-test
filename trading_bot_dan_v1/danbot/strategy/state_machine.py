from __future__ import annotations

from enum import Enum


class MarketState(str, Enum):
    BUILDUP = "BUILDUP"
    IMPULSE = "IMPULSE"
    CLIMAX = "CLIMAX"
    EXHAUSTION = "EXHAUSTION"
    REBALANCE = "REBALANCE"


class ImpulseLifecycleMachine:
    def __init__(self) -> None:
        self.state = MarketState.BUILDUP

    def transition(self, impulse: bool, climax: bool, exhaustion: bool, rebalance: bool) -> MarketState:
        if self.state == MarketState.BUILDUP and impulse:
            self.state = MarketState.IMPULSE
        elif self.state == MarketState.IMPULSE and climax:
            self.state = MarketState.CLIMAX
        elif self.state in (MarketState.IMPULSE, MarketState.CLIMAX) and exhaustion:
            self.state = MarketState.EXHAUSTION
        elif self.state == MarketState.EXHAUSTION and rebalance:
            self.state = MarketState.REBALANCE
        elif self.state == MarketState.REBALANCE and not impulse:
            self.state = MarketState.BUILDUP
        return self.state
