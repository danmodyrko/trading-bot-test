import asyncio

from danbot.exchange.models import OrderRequest, Side
from danbot.strategy.execution import ExecutionEngine, SlippageModel, SymbolFilters
from danbot.strategy.risk import RiskManager


def _engine() -> ExecutionEngine:
    rm = RiskManager(3.0, 3, 1.0, 500, 10)
    model = SlippageModel(max_slippage_bps=8.0, spread_guard_bps=15.0, edge_safety_factor=0.7)
    return ExecutionEngine(rm, model)


def test_slippage_rejects_when_cost_exceeds_edge():
    model = SlippageModel(max_slippage_bps=8.0, spread_guard_bps=15.0, edge_safety_factor=0.7)
    expected = model.expected_slippage_bps(order_size=100, spread_bps=4, volatility=0.01, depth=None, impact=0.00005)
    ok, reason = model.validate(expected_bps=expected, spread_bps=4, expected_edge_bps=2.0)
    assert not ok
    assert reason in {"slippage_guard", "cost_exceeds_edge"}


def test_execution_engine_idempotency_returns_same_record():
    engine = _engine()

    async def submit(order, price):
        return {"ok": True, "qty": order.qty, "price": price}

    async def run():
        req = OrderRequest(symbol="BTCUSDT", side=Side.BUY, qty=0.123456)
        filters = SymbolFilters(tick_size=0.1, step_size=0.01, min_notional=5)
        first = await engine.place_order(req, 100.456, 3.0, 20.0, 0.001, 0.0, None, filters, submit)
        second = await engine.place_order(req, 100.456, 3.0, 20.0, 0.001, 0.0, None, filters, submit)
        assert first.idempotency_key == second.idempotency_key
        assert first.status == second.status == "FILLED"

    asyncio.run(run())
