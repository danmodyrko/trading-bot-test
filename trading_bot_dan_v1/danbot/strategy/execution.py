from __future__ import annotations

import asyncio
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Any

from danbot.exchange.models import OrderRequest, Side
from danbot.strategy.risk import RiskManager


@dataclass
class SlippageModel:
    max_slippage_bps: float
    spread_guard_bps: float
    edge_safety_factor: float

    def expected_slippage_bps(self, order_size: float, spread_bps: float, volatility: float, depth: float | None, impact: float) -> float:
        if depth and depth > 0:
            depth_component = (order_size / depth) * 10_000
            return spread_bps * 0.5 + depth_component + volatility * 10_000 * 0.15
        return spread_bps * 0.5 + impact * order_size * 10_000 + volatility * 10_000 * 0.15

    def validate(self, expected_bps: float, spread_bps: float, expected_edge_bps: float) -> tuple[bool, str]:
        if spread_bps > self.spread_guard_bps:
            return False, "spread_guard"
        if expected_bps > self.max_slippage_bps:
            return False, "slippage_guard"
        if expected_bps > expected_edge_bps * self.edge_safety_factor:
            return False, "cost_exceeds_edge"
        return True, "ok"


@dataclass
class SymbolFilters:
    tick_size: float
    step_size: float
    min_notional: float


@dataclass
class TradeTimestamps:
    signal_time: str
    decision_time: str
    send_time: str | None = None
    ack_time: str | None = None
    fill_time: str | None = None


@dataclass
class TradeRecord:
    correlation_id: str
    idempotency_key: str
    symbol: str
    side: str
    qty: float
    price: float
    status: str
    reason: str
    timestamps: TradeTimestamps
    extra: dict[str, Any] = field(default_factory=dict)


class ExecutionEngine:
    def __init__(self, risk: RiskManager, slippage: SlippageModel, retries: int = 3, retry_base_delay_s: float = 0.2, max_dedup_entries: int = 2000) -> None:
        self.risk = risk
        self.slippage = slippage
        self.retries = retries
        self.retry_base_delay_s = retry_base_delay_s
        self.max_dedup_entries = max_dedup_entries
        self._idempotency_cache: dict[str, TradeRecord] = {}

    async def place_order(
        self,
        order: OrderRequest,
        mark_price: float,
        spread_bps: float,
        expected_edge_bps: float,
        volatility: float,
        impact: float,
        depth: float | None,
        symbol_filters: SymbolFilters,
        submit_fn,
        signal_time: str | None = None,
    ) -> TradeRecord:
        decision_time = datetime.now(timezone.utc).isoformat()
        signal_time = signal_time or decision_time
        normalized_qty = self._quantize(order.qty, symbol_filters.step_size)
        normalized_price = self._quantize(mark_price, symbol_filters.tick_size)
        notional = normalized_qty * normalized_price
        key = f"{order.symbol}:{order.side.value}:{normalized_qty}:{round(normalized_price, 8)}"
        if key in self._idempotency_cache:
            return self._idempotency_cache[key]

        if notional < symbol_filters.min_notional:
            record = self._blocked(order, normalized_qty, normalized_price, signal_time, decision_time, "min_notional")
            return self._cache(key, record)

        expected = self.slippage.expected_slippage_bps(normalized_qty, spread_bps, volatility, depth, impact)
        slippage_ok, slippage_reason = self.slippage.validate(expected, spread_bps, expected_edge_bps)
        can_trade, risk_reason = self.risk.can_trade(order.symbol, notional, spread_blocked=spread_bps > self.slippage.spread_guard_bps, slippage_blocked=not slippage_ok)
        if not slippage_ok or not can_trade:
            reason = slippage_reason if not slippage_ok else risk_reason
            record = self._blocked(order, normalized_qty, normalized_price, signal_time, decision_time, reason)
            return self._cache(key, record)

        correlation_id = str(uuid.uuid4())
        ts = TradeTimestamps(signal_time=signal_time, decision_time=decision_time)
        for attempt in range(self.retries + 1):
            ts.send_time = datetime.now(timezone.utc).isoformat()
            try:
                ack = await submit_fn(OrderRequest(symbol=order.symbol, side=order.side, qty=normalized_qty, reduce_only=order.reduce_only), normalized_price)
                ts.ack_time = datetime.now(timezone.utc).isoformat()
                ts.fill_time = ts.ack_time
                self.risk.apply_trade_open(order.symbol, notional)
                record = TradeRecord(
                    correlation_id=correlation_id,
                    idempotency_key=key,
                    symbol=order.symbol,
                    side=order.side.value,
                    qty=normalized_qty,
                    price=normalized_price,
                    status="FILLED",
                    reason="ok",
                    timestamps=ts,
                    extra={"attempt": attempt, "ack": ack},
                )
                return self._cache(key, record)
            except Exception as exc:  # pragma: no cover
                if attempt >= self.retries:
                    record = TradeRecord(
                        correlation_id=correlation_id,
                        idempotency_key=key,
                        symbol=order.symbol,
                        side=order.side.value,
                        qty=normalized_qty,
                        price=normalized_price,
                        status="REJECTED",
                        reason=f"submit_error:{exc}",
                        timestamps=ts,
                        extra={"attempt": attempt},
                    )
                    return self._cache(key, record)
                delay = self.retry_base_delay_s * (2**attempt) + random.uniform(0.01, 0.2)
                await asyncio.sleep(delay)

        return self._blocked(order, normalized_qty, normalized_price, signal_time, decision_time, "unknown")

    def _cache(self, key: str, record: TradeRecord) -> TradeRecord:
        self._idempotency_cache[key] = record
        if len(self._idempotency_cache) > self.max_dedup_entries:
            oldest = next(iter(self._idempotency_cache))
            self._idempotency_cache.pop(oldest, None)
        return record

    def _blocked(self, order: OrderRequest, qty: float, price: float, signal_time: str, decision_time: str, reason: str) -> TradeRecord:
        return TradeRecord(
            correlation_id=str(uuid.uuid4()),
            idempotency_key=f"blocked:{time.time_ns()}",
            symbol=order.symbol,
            side=order.side.value,
            qty=qty,
            price=price,
            status="BLOCKED",
            reason=reason,
            timestamps=TradeTimestamps(signal_time=signal_time, decision_time=decision_time),
        )

    @staticmethod
    def _quantize(value: float, step: float) -> float:
        if step <= 0:
            return value
        q = Decimal(str(value)) / Decimal(str(step))
        return float((q.quantize(Decimal("1"), rounding=ROUND_DOWN) * Decimal(str(step))).normalize())


def make_reduce_only_exit(symbol: str, side: Side, qty: float) -> OrderRequest:
    closing_side = Side.SELL if side == Side.BUY else Side.BUY
    return OrderRequest(symbol=symbol, side=closing_side, qty=qty, reduce_only=True)
