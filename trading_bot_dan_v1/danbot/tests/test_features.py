from datetime import datetime, timezone, timedelta

from danbot.data.candles import Candle
from danbot.data.feature_engine import FeatureEngine


def test_feature_engine_returns_exhaustion_ratio():
    fe = FeatureEngine()
    c1 = Candle("BTCUSDT", datetime.now(timezone.utc), 100, 101, 99, 100, 10)
    c2 = Candle("BTCUSDT", datetime.now(timezone.utc) + timedelta(minutes=1), 100, 102, 99, 101, 50)
    fe.on_candle(c1, None)
    out = fe.on_candle(c2, c1)
    assert "exhaustion_ratio" in out
    assert out["volume_zscore"] >= 0
