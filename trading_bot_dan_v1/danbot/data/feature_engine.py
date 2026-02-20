from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from danbot.core.utils import zscore
from danbot.data.candles import Candle


@dataclass
class SymbolFeatures:
    returns: deque[float] = field(default_factory=lambda: deque(maxlen=120))
    volumes: deque[float] = field(default_factory=lambda: deque(maxlen=120))
    velocities: deque[float] = field(default_factory=lambda: deque(maxlen=120))


class FeatureEngine:
    def __init__(self) -> None:
        self.state: dict[str, SymbolFeatures] = {}

    def on_candle(self, candle: Candle, previous: Candle | None) -> dict[str, float]:
        features = self.state.setdefault(candle.symbol, SymbolFeatures())
        ret = 0.0 if previous is None else (candle.close - previous.close) / max(previous.close, 1e-9) * 100
        velocity = abs(candle.close - candle.open) / 60
        features.returns.append(ret)
        features.volumes.append(candle.volume)
        features.velocities.append(velocity)
        vol_z = zscore(candle.volume, features.volumes)
        max_vel = max(features.velocities) if features.velocities else velocity
        exhaustion_ratio = velocity / max(max_vel, 1e-9)
        wick_ratio = (candle.high - candle.low) / max(abs(candle.close - candle.open), 1e-9)
        return {
            "return_pct": ret,
            "volume_zscore": vol_z,
            "velocity": velocity,
            "max_velocity": max_vel,
            "exhaustion_ratio": exhaustion_ratio,
            "wick_ratio": wick_ratio,
        }
