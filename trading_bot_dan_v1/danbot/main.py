from __future__ import annotations

import argparse
import asyncio
import logging
import os
import random
from datetime import datetime, timezone

from danbot.core.config import load_config
from danbot.core.logging import setup_logging
from danbot.data.aggregations import MinuteCandleBuilder
from danbot.data.feature_engine import FeatureEngine
from danbot.exchange.models import OrderRequest, Side, Tick
from danbot.exchange.paper_sim import PaperSimulator
from danbot.storage.db import Database
from danbot.strategy.reversal_strategy import ReversalStrategy
from danbot.strategy.risk import RiskManager

logger = logging.getLogger(__name__)


async def run_headless() -> None:
    config = load_config()
    db = Database(config.storage.sqlite_path)
    db.init(os.path.join(os.path.dirname(__file__), "storage", "schema.sql"))
    strategy = ReversalStrategy(config.strategy)
    risk = RiskManager(
        max_daily_loss_pct=config.risk.max_daily_loss_pct,
        max_positions=config.risk.max_positions,
        max_trade_risk_pct=config.risk.max_trade_risk_pct,
        max_notional_per_trade=config.risk.max_notional_per_trade,
        cooldown_seconds=config.risk.cooldown_seconds,
    )
    sim = PaperSimulator()
    candles = MinuteCandleBuilder()
    features = FeatureEngine()
    prices = {s: 100.0 + i * 10 for i, s in enumerate(config.symbols)}

    for _ in range(200):
        for symbol in config.symbols:
            prices[symbol] += random.uniform(-0.6, 0.8)
            tick = Tick(symbol=symbol, price=prices[symbol], qty=random.uniform(0.1, 2.0), ts=datetime.now(timezone.utc))
            closed = candles.update(tick)
            if closed:
                arr = candles.candles.get(symbol)
                prev = arr[-2] if arr and len(arr) > 1 else None
                f = features.on_candle(closed, prev)
                signal = strategy.evaluate(symbol, f, imbalance_factor=0.5, structure_confirmed=True)
                db.insert_signal(datetime.now(timezone.utc).isoformat(), signal)
                can_trade, reason = risk.can_trade()
                if signal.side and can_trade:
                    side = Side.BUY if signal.side == "BUY" else Side.SELL
                    order = OrderRequest(symbol=symbol, side=side, qty=0.01)
                    sim.place_order(order, mark_price=tick.price)
                elif not can_trade:
                    db.insert_incident(datetime.now(timezone.utc).isoformat(), "WARN", "trade_blocked", reason)
        await asyncio.sleep(0.1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    setup_logging()
    config = load_config()
    if args.headless:
        asyncio.run(run_headless())
    else:
        try:
            from danbot.ui.app import launch_ui

            launch_ui(config)
        except Exception as exc:
            logger.error("UI unavailable (%s). Falling back to headless.", exc)
            asyncio.run(run_headless())


if __name__ == "__main__":
    main()
