from __future__ import annotations

import argparse
import asyncio
import logging
import os
import random
from datetime import datetime, timezone

from danbot.core.config import load_config
from danbot.core.logging import setup_logging
from danbot.data.tick_features import TickFeatureEngine, TradeTick
from danbot.exchange.binance_client import build_clients, discover_usdtm_symbols
from danbot.exchange.models import OrderRequest, Side
from danbot.exchange.paper_sim import PaperSimulator
from danbot.storage.db import Database
from danbot.strategy.execution import SlippageModel
from danbot.strategy.reversal_strategy import ReversalStrategy
from danbot.strategy.risk import RiskManager
from danbot.strategy.spike_classifier import classify_spike

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
    slippage_model = SlippageModel(
        max_slippage_bps=config.execution.max_slippage_bps,
        spread_guard_bps=config.execution.spread_guard_bps,
        edge_safety_factor=config.execution.edge_safety_factor,
    )
    sim = PaperSimulator()
    tick_engine = TickFeatureEngine(
        impulse_threshold_pct=config.strategy.impulse_threshold_pct,
        impulse_window_seconds=config.strategy.impulse_window_seconds,
        volume_z_threshold=config.strategy.volume_zscore_threshold,
        trade_rate_burst=config.strategy.trade_rate_burst_threshold,
    )

    symbols = config.symbols
    if config.auto_discover_symbols:
        try:
            clients = build_clients(config)
            symbols, watch_only = await discover_usdtm_symbols(clients.rest, config.min_quote_volume_24h, config.max_symbols_active)
            logger.info("Discovered %s active symbols and %s watch-only symbols", len(symbols), len(watch_only))
        except Exception as exc:
            logger.warning("Symbol discovery failed: %s", exc)

    prices = {s: 100.0 + i * 10 for i, s in enumerate(symbols)}
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    for i in range(200):
        for symbol in symbols:
            prices[symbol] += random.uniform(-0.35, 0.45)
            now_ms += 100
            spread_bps = abs(random.gauss(4.0, 1.5))
            tick = TradeTick(
                symbol=symbol,
                ts_ms=now_ms,
                price=prices[symbol],
                qty=random.uniform(0.1, 4.0),
                buyer_maker=bool(random.getrandbits(1)),
                spread_bps=spread_bps,
            )
            snap = tick_engine.on_trade(tick, expected_order_size=0.25)
            features = snap.__dict__
            regime_ok = True  # placeholder for EMA20/EMA100 ATR regime filter
            signal = strategy.evaluate(symbol, features, structure_confirmed=(i % 4 == 0), regime_ok=regime_ok)
            db.insert_signal(datetime.now(timezone.utc).isoformat(), signal)

            spike = classify_spike(snap.wick_proxy, snap.trade_rate / max(config.strategy.trade_rate_burst_threshold, 1e-9), snap.imbalance_factor, snap.spread_norm, abs(snap.accel))
            slippage = slippage_model.expected_slippage_bps(0.25, snap.spread_bps, snap.vol_10s, None, snap.impact)
            slippage_ok, slippage_reason = slippage_model.validate(slippage, snap.spread_bps, expected_edge_bps=max(snap.impulse_score * 100, 1.0))
            vol_blocked = risk.update_volatility(snap.vol_10s, config.strategy.vol_kill_threshold, config.strategy.vol_cooldown_seconds)

            can_trade, risk_reason = risk.can_trade(stale=False, spread_blocked=snap.spread_bps > config.execution.spread_guard_bps, slippage_blocked=not slippage_ok)
            reasons = [slippage_reason if not slippage_ok else "ok", risk_reason]

            if signal.side and can_trade:
                side = Side.BUY if signal.side == "BUY" else Side.SELL
                qty = risk.position_size(1000, signal.confidence, 0.35, size_multiplier=spike.recommended_size_multiplier) / max(tick.price, 1e-9)
                order = OrderRequest(symbol=symbol, side=side, qty=qty)
                if config.execution.dry_run or (config.mode.value == "REAL" and not config.execution.enable_real_orders):
                    db.insert_lifelog(datetime.now(timezone.utc).isoformat(), "SIGNAL", "SIGNAL", "dry-run order blocked", symbol, reasons, metrics={"qty": qty})
                else:
                    sim.place_order(order, mark_price=tick.price)
                    db.insert_lifelog(datetime.now(timezone.utc).isoformat(), "SIGNAL", "SIGNAL", "entry placed", symbol, reasons)
            elif vol_blocked or not can_trade:
                db.insert_lifelog(datetime.now(timezone.utc).isoformat(), "RISK", "RISK", "entry blocked", symbol, reasons, metrics={"vol_10s": snap.vol_10s})

            db.insert_health_metric(datetime.now(timezone.utc).isoformat(), latency_ms=50, stale_flag=False, positions_count=risk.open_positions, daily_loss_pct=risk.loss_today_pct)
        await asyncio.sleep(0.02)


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
