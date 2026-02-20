from danbot.strategy.execution import SlippageModel


def test_slippage_rejects_when_cost_exceeds_edge():
    model = SlippageModel(max_slippage_bps=8.0, spread_guard_bps=15.0, edge_safety_factor=0.7)
    expected = model.expected_slippage_bps(order_size=100, spread_bps=4, volatility=0.01, depth=None, impact=0.00005)
    ok, reason = model.validate(expected_bps=expected, spread_bps=4, expected_edge_bps=2.0)
    assert not ok
    assert reason in {"slippage_guard", "cost_exceeds_edge"}
