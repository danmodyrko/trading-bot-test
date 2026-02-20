from danbot.data.tick_features import TickFeatureEngine, TradeTick


def test_tick_feature_engine_outputs_impulse_fields():
    fe = TickFeatureEngine(impulse_threshold_pct=0.2, impulse_window_seconds=60, volume_z_threshold=-10, trade_rate_burst=0.1)
    out = None
    ts = 1_700_000_000_000
    price = 100.0
    for i in range(40):
        price += 0.15
        out = fe.on_trade(TradeTick(symbol="BTCUSDT", ts_ms=ts + i * 200, price=price, qty=2.0, buyer_maker=False, spread_bps=5.0))
    assert out is not None
    assert out.impulse_score >= 0
    assert isinstance(out.exhaustion_detected, bool)
    assert out.trade_rate > 0
