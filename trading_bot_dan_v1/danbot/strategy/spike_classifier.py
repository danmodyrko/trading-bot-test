from __future__ import annotations


def classify_spike(wick_ratio: float, trade_burst: float, imbalance: float, refill_speed: float, variance: float) -> tuple[str, float]:
    if trade_burst > 2.5 and variance > 2.0:
        return "news-like", 0.5
    if wick_ratio > 3 and refill_speed < 0.5:
        return "spoof-like", 0.4
    if imbalance > 0.7 and trade_burst > 1.8:
        return "liquidation-like", 0.8
    return "breakout-like", 0.65
