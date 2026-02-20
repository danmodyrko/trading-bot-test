from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from statistics import median


@dataclass
class TradeTick:
    symbol: str
    ts_ms: int
    price: float
    qty: float
    buyer_maker: bool
    trade_count: int = 1
    spread_bps: float = 0.0


@dataclass
class FeatureSnapshot:
    symbol: str
    ts_ms: int
    price_change_pct: float
    price_velocity: float
    accel: float
    trade_rate: float
    volume_5s: float
    volume_10s: float
    volume_zscore: float
    imbalance_factor: float
    wick_proxy: float
    spread_bps: float
    spread_norm: float
    impact: float
    expected_slippage_bps: float
    vol_10s: float
    impulse_score: float
    impulse_detected: bool
    exhaustion_ratio: float
    exhaustion_detected: bool


def _robust_zscore(value: float, values: list[float]) -> float:
    if len(values) < 10:
        return 0.0
    med = median(values)
    mad = median(abs(v - med) for v in values)
    if mad <= 1e-9:
        return 0.0
    return 0.6745 * (value - med) / mad


@dataclass
class SymbolTickState:
    trades_120s: deque[TradeTick] = field(default_factory=lambda: deque())
    spreads_120s: deque[float] = field(default_factory=lambda: deque(maxlen=1200))
    velocities: deque[float] = field(default_factory=lambda: deque(maxlen=1200))


class TickFeatureEngine:
    def __init__(self, impulse_threshold_pct: float, impulse_window_seconds: int, volume_z_threshold: float, trade_rate_burst: float = 8.0) -> None:
        self.state: dict[str, SymbolTickState] = {}
        self.impulse_threshold_pct = impulse_threshold_pct
        self.impulse_window_seconds = impulse_window_seconds
        self.volume_z_threshold = volume_z_threshold
        self.trade_rate_burst = trade_rate_burst

    def on_trade(self, tick: TradeTick, expected_order_size: float = 1.0) -> FeatureSnapshot:
        s = self.state.setdefault(tick.symbol, SymbolTickState())
        s.trades_120s.append(tick)
        s.spreads_120s.append(tick.spread_bps)
        cutoff_120s = tick.ts_ms - 120_000
        while s.trades_120s and s.trades_120s[0].ts_ms < cutoff_120s:
            s.trades_120s.popleft()

        trades = list(s.trades_120s)
        p_now = tick.price

        def recent(sec: int) -> list[TradeTick]:
            cutoff = tick.ts_ms - sec * 1000
            return [t for t in trades if t.ts_ms >= cutoff]

        t3 = recent(3)
        t5 = recent(5)
        t10 = recent(10)
        t60 = recent(min(self.impulse_window_seconds, 60))
        if t3:
            dt = max((tick.ts_ms - t3[0].ts_ms) / 1000.0, 1e-6)
            velocity = abs(p_now - t3[0].price) / dt
        else:
            velocity = 0.0
        prev_velocity = s.velocities[-1] if s.velocities else velocity
        s.velocities.append(velocity)
        accel = velocity - prev_velocity

        trade_rate = len(t3) / 3.0
        volume_5s = sum(t.qty for t in t5)
        volume_10s = sum(t.qty for t in t10)

        vols_10s: list[float] = []
        for i in range(10, 121, 10):
            bucket = [t.qty for t in trades if tick.ts_ms - i * 1000 <= t.ts_ms < tick.ts_ms - (i - 10) * 1000]
            vols_10s.append(sum(bucket))
        volume_z = _robust_zscore(volume_10s, vols_10s)

        taker_buy = sum(t.qty for t in t10 if not t.buyer_maker)
        taker_sell = sum(t.qty for t in t10 if t.buyer_maker)
        tot = max(taker_buy + taker_sell, 1e-9)
        imbalance = (taker_buy - taker_sell) / tot

        high = max((t.price for t in t10), default=p_now)
        low = min((t.price for t in t10), default=p_now)
        wick_proxy = (high - low) / max(abs(p_now), 1e-9)

        spread_baseline = median(s.spreads_120s) if s.spreads_120s else max(tick.spread_bps, 1e-9)
        spread_norm = tick.spread_bps / max(spread_baseline, 1e-9)

        impacts = [abs((b.price - a.price) / max(a.price, 1e-9)) / max(b.qty, 1e-9) for a, b in zip(t10, t10[1:])]
        impact = median(impacts) if impacts else 0.0
        expected_slippage_bps = impact * expected_order_size * 10_000

        returns = [
            __import__("math").log(max(b.price, 1e-9) / max(a.price, 1e-9))
            for a, b in zip(t10, t10[1:])
        ]
        vol_10s = (__import__("math").sqrt(sum(r * r for r in returns) / max(len(returns), 1)) if returns else 0.0)

        window_start = t60[0].price if t60 else p_now
        price_change_pct = (p_now - window_start) / max(window_start, 1e-9) * 100
        impulse_score = (abs(price_change_pct) / max(min(self.impulse_window_seconds, 60), 1)) * max(volume_z, 0.0) * (1 + abs(imbalance))
        impulse_detected = abs(price_change_pct) >= self.impulse_threshold_pct and volume_z >= self.volume_z_threshold and trade_rate >= self.trade_rate_burst

        max_vel = max(s.velocities) if s.velocities else velocity
        exhaustion_ratio = velocity / max(max_vel, 1e-9)
        divergence = len(t10) >= 2 and (abs(imbalance) < 0.1 and abs(price_change_pct) > 0.25)
        wick_expansion = wick_proxy > 0.001
        spread_normalized = spread_norm < 1.1
        exhaustion_detected = exhaustion_ratio < 0.4 and (divergence or wick_expansion or spread_normalized)

        return FeatureSnapshot(
            symbol=tick.symbol,
            ts_ms=tick.ts_ms,
            price_change_pct=price_change_pct,
            price_velocity=velocity,
            accel=accel,
            trade_rate=trade_rate,
            volume_5s=volume_5s,
            volume_10s=volume_10s,
            volume_zscore=volume_z,
            imbalance_factor=imbalance,
            wick_proxy=wick_proxy,
            spread_bps=tick.spread_bps,
            spread_norm=spread_norm,
            impact=impact,
            expected_slippage_bps=expected_slippage_bps,
            vol_10s=vol_10s,
            impulse_score=impulse_score,
            impulse_detected=impulse_detected,
            exhaustion_ratio=exhaustion_ratio,
            exhaustion_detected=exhaustion_detected,
        )
