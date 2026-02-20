from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SpikeClassification:
    label: str
    confidence: float
    recommended_size_multiplier: float


def classify_spike(wick_proxy: float, trade_rate_burst: float, imbalance: float, spread_expansion: float, variance: float) -> SpikeClassification:
    if trade_rate_burst > 3.0 and variance > 2.5 and spread_expansion > 1.6:
        return SpikeClassification("news-like", 0.75, 0.35)
    if wick_proxy > 0.003 and spread_expansion > 1.3 and imbalance < 0.2:
        return SpikeClassification("spoof-like", 0.65, 0.5)
    if abs(imbalance) > 0.65 and trade_rate_burst > 2.2:
        return SpikeClassification("liquidation-like", 0.85, 0.7)
    return SpikeClassification("organic-breakout", 0.6, 1.0)
