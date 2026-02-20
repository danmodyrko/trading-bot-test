from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ImpulseSignal:
    detected: bool
    direction: int
    score: float


def detect_impulse(price_change_pct: float, seconds: float, volume_z: float, imbalance_factor: float, threshold_pct: float) -> ImpulseSignal:
    direction = 1 if price_change_pct > 0 else -1
    score = (abs(price_change_pct) / max(seconds, 1e-9)) * max(volume_z, 0) * max(imbalance_factor, 0.1)
    detected = abs(price_change_pct) >= threshold_pct and volume_z > 0
    return ImpulseSignal(detected=detected, direction=direction, score=score)
