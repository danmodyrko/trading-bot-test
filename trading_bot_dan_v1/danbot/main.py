from __future__ import annotations

import argparse
import asyncio
import logging
import os
import random
from datetime import datetime, timezone

from danbot.core.config import load_config
from danbot.core.events import EventRecord, get_event_bus
from danbot.core.logging import setup_logging
from danbot.data.tick_features import TickFeatureEngine, TradeTick
from danbot.exchange.binance_client import build_clients, discover_usdtm_symbols
from danbot.exchange.models import OrderRequest, Side
from danbot.exchange.paper_sim import PaperSimulator
from danbot.storage.db import Database
from danbot.storage.runtime_state import SnapshotStore, TradeJournal
from danbot.strategy.execution import ExecutionEngine, SlippageModel, SymbolFilters
from danbot.strategy.reversal_strategy import ReversalStrategy
from danbot.strategy.risk import RiskManager
from danbot.strategy.spike_classifier import classify_spike

logger = logging.getLogger(__name__)


async def run_headless() -> None:
    config = load_config()
    event_bus = get_event_bus()
    db = Database(config.storage.sqlite_path)
    db.init(os.path.join(os.path.dirname(__file__), "storage", "schema.sql"))
    strategy = ReversalStrategy(config.strategy)
    risk = RiskManager(
        max_daily_loss_pct=config.risk.max_daily_loss_pct,
        max_positions=config.risk.max_positions,
        max_trade_risk_pct=config.risk.max_trade_risk_pct,
        max_notional_per_trade=config.risk.max_notional_per_trade,
        cooldown_seconds=config.risk.cooldown_seconds,
        max_positions_per_symbol=config.risk.max_positions_per_symbol,
        max_exposure_per_symbol=config.risk.max_exposure_per_symbol,
        max_account_exposure=config.risk.max_account_exposure,
        max_consecutive_losses=config.risk.max_consecutive_losses,
        loss_cooldown_seconds=config.risk.loss_cooldown_seconds,
        include_unrealized_pnl=config.risk.include_unrealized_pnl,
    )
    slippage_model = SlippageModel(
        max_slippage_bps=config.execution.max_slippage_bps,
        spread_guard_bps=config.execution.spread_guard_bps,
        edge_safety_factor=config.execution.edge_safety_factor,
    )
    execution_engine = ExecutionEngine(
        risk=risk,
        slippage=slippage_model,
        retries=config.execution.max_retry_attempts,
        retry_base_delay_s=config.execution.retry_base_delay_s,
    )
    sim = PaperSimulator()
    snapshot_store = SnapshotStore(config.storage.snapshots_path)
    trade_journal = TradeJournal(config.storage.trade_journal_path)
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

    async def submit_fn(order: OrderRequest, price: float):
        return sim.place_order(order, mark_price=price).__dict__

    prices = {s: 100.0 + i * 10 for i, s in enumerate(symbols)}
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    for i in range(200):
        for symbol in symbols:
            prices[symbol] += random.uniform(-0.35, 0.45)
            now_ms += 100
            spread_bps = abs(random.gauss(4.0, 1.5))
            tick = TradeTick(symbol=symbol, ts_ms=now_ms, price=prices[symbol], qty=random.uniform(0.1, 4.0), buyer_maker=bool(random.getrandbits(1)), spread_bps=spread_bps)
            snap = tick_engine.on_trade(tick, expected_order_size=0.25)
            features = snap.__dict__
            signal_time = datetime.now(timezone.utc).isoformat()
            signal = strategy.evaluate(symbol, features, structure_confirmed=(i % 4 == 0), regime_ok=True)
            db.insert_signal(signal_time, signal)

            spike = classify_spike(snap.wick_proxy, snap.trade_rate / max(config.strategy.trade_rate_burst_threshold, 1e-9), snap.imbalance_factor, snap.spread_norm, abs(snap.accel))
            vol_blocked = risk.update_volatility(snap.vol_10s, config.strategy.vol_kill_threshold, config.strategy.vol_cooldown_seconds)
            risk.update_pnl(risk.loss_today_pct, unrealized_pct=0.0)

            if signal.side:
                side = Side.BUY if signal.side == "BUY" else Side.SELL
                qty = risk.position_size(1000, signal.confidence, 0.35, size_multiplier=spike.recommended_size_multiplier) / max(tick.price, 1e-9)
                trade = await execution_engine.place_order(
                    order=OrderRequest(symbol=symbol, side=side, qty=qty),
                    mark_price=tick.price,
                    spread_bps=snap.spread_bps,
                    expected_edge_bps=max(snap.impulse_score * 100, 1.0),
                    volatility=snap.vol_10s,
                    impact=snap.impact,
                    depth=None,
                    symbol_filters=SymbolFilters(tick_size=0.01, step_size=0.001, min_notional=5.0),
                    submit_fn=submit_fn,
                    signal_time=signal_time,
                )
                if config.execution.dry_run or (config.mode.value == "REAL" and not config.execution.enable_real_orders):
                    trade.status = "BLOCKED"
                    trade.reason = "dry_run"

                details = {
                    "status": trade.status,
                    "reason": trade.reason,
                    "qty": trade.qty,
                    "side": trade.side,
                    "latency": trade.timestamps.__dict__,
                }
                event_bus.publish(EventRecord(action="ORDER", message=f"order {trade.status.lower()}", category="ORDER", symbol=symbol, correlation_id=trade.correlation_id, details=details))
                db.insert_lifelog(datetime.now(timezone.utc).isoformat(), "INFO" if trade.status == "FILLED" else "WARNING", "ORDER", trade.reason, symbol, [trade.reason], metrics=details)
            elif vol_blocked:
                event_bus.publish(EventRecord(action="RISK_BLOCK", message="entry blocked", category="RISK", severity="WARNING", symbol=symbol, details={"reason": "volatility"}))

            if i % 10 == 0:
                snapshot_store.save(
                    {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "positions": risk.snapshot(),
                        "pending_orders": [],
                        "cooldowns": risk.snapshot().get("cooldown_until", {}),
                        "last_event_ts": now_ms,
                    }
                )

            if i % 15 == 0:
                trade_journal.append_completed_trade(
                    {
                        "entry_time": signal_time,
                        "exit_time": datetime.now(timezone.utc).isoformat(),
                        "symbol": symbol,
                        "side": signal.side or "",
                        "size": round(random.uniform(0.01, 0.05), 4),
                        "entry_price": round(tick.price, 2),
                        "exit_price": round(tick.price + random.uniform(-0.4, 0.4), 2),
                        "fees": 0.02,
                        "pnl": round(random.uniform(-1.5, 2.0), 3),
                        "mfe": round(random.uniform(0.1, 1.2), 3),
                        "mae": round(random.uniform(-1.1, -0.1), 3),
                        "slippage": round(random.uniform(0.0, 1.5), 3),
                        "reason": "strategy_exit",
                        "model_score": round(signal.confidence, 3),
                        "correlation_id": "simulated",
                    }
                )

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
