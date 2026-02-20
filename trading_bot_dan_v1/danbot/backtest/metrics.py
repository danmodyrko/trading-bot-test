from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BacktestMetrics:
    winrate: float
    expectancy: float
    max_drawdown: float
    profit_factor: float
    avg_hold_seconds: float
