from danbot.strategy.risk import RiskManager


def test_risk_blocks_daily_loss():
    rm = RiskManager(2.0, 2, 0.5, 100, 30, loss_today_pct=2.2)
    ok, reason = rm.can_trade()
    assert not ok
    assert reason == "daily_loss_circuit_breaker"


def test_position_size_capped_with_multiplier():
    rm = RiskManager(2.0, 2, 1.0, 100, 30)
    assert rm.position_size(10_000, confidence=1.0, stop_distance_pct=1.0, size_multiplier=1.2) == 100


def test_volatility_kill_switch_triggers_block():
    rm = RiskManager(2.0, 2, 1.0, 100, 30)
    assert rm.update_volatility(0.03, threshold=0.02, cooldown_seconds=30)
    ok, reason = rm.can_trade()
    assert not ok
    assert reason == "volatility_block"
