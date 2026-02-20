from __future__ import annotations

from dataclasses import dataclass

from danbot.backtest.metrics import BacktestMetrics
from danbot.data.feature_engine import FeatureEngine
from danbot.strategy.reversal_strategy import ReversalStrategy


@dataclass
class BacktestResult:
    equity_curve: list[float]
    metrics: BacktestMetrics


def run_backtest(candles, strategy: ReversalStrategy, initial_equity: float = 10_000) -> BacktestResult:
    engine = FeatureEngine()
    equity = initial_equity
    peak = equity
    curve = [equity]
    wins = losses = 0
    pnl_sum = 0.0
    for i, c in enumerate(candles):
        prev = candles[i - 1] if i > 0 else None
        f = engine.on_candle(c, prev)
        sig = strategy.evaluate(c.symbol, f, imbalance_factor=0.5, structure_confirmed=True)
        if sig.side:
            trade_pnl = -0.1 if sig.side == "SELL" else 0.1
            equity += trade_pnl
            pnl_sum += trade_pnl
            wins += trade_pnl > 0
            losses += trade_pnl <= 0
            peak = max(peak, equity)
            curve.append(equity)
    gross_profit = max(pnl_sum, 0.0)
    gross_loss = abs(min(pnl_sum, 0.0)) or 1e-9
    dd = min((x - peak) for x in curve)
    total = max(wins + losses, 1)
    metrics = BacktestMetrics(
        winrate=wins / total,
        expectancy=pnl_sum / total,
        max_drawdown=abs(dd),
        profit_factor=gross_profit / gross_loss,
        avg_hold_seconds=60,
    )
    return BacktestResult(curve, metrics)
