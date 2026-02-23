from danbot.strategy.risk import RiskManager


def _rm() -> RiskManager:
    return RiskManager(
        max_daily_loss_pct=2.0,
        max_positions=2,
        max_trade_risk_pct=1.0,
        max_notional_per_trade=100,
        cooldown_seconds=30,
    )


def test_risk_blocks_daily_loss():
    rm = _rm()
    rm.update_pnl(realized_pct=2.2)
    ok, reason = rm.can_trade(symbol="BTCUSDT", notional=10)
    assert not ok
    assert reason == "daily_loss_circuit_breaker"


def test_position_size_capped_with_multiplier():
    rm = _rm()
    assert rm.position_size(10_000, confidence=1.0, stop_distance_pct=1.0, size_multiplier=1.2) == 100


def test_volatility_kill_switch_triggers_block():
    rm = _rm()
    assert rm.update_volatility(0.03, threshold=0.02, cooldown_seconds=30)
    ok, reason = rm.can_trade(symbol="BTCUSDT", notional=10)
    assert not ok
    assert reason == "volatility_block"


def test_symbol_position_limit_blocks():
    rm = _rm()
    rm.apply_trade_open("BTCUSDT", 30)
    ok, reason = rm.can_trade(symbol="BTCUSDT", notional=10)
    assert not ok
    assert reason == "max_positions_per_symbol"
