from __future__ import annotations

from collections import deque

from danbot.data.candles import Candle
from danbot.exchange.models import Tick


class MinuteCandleBuilder:
    def __init__(self, maxlen: int = 1440) -> None:
        self.candles: dict[str, deque[Candle]] = {}
        self._current: dict[str, Candle] = {}
        self.maxlen = maxlen

    def update(self, tick: Tick) -> Candle | None:
        minute = tick.ts.replace(second=0, microsecond=0)
        cur = self._current.get(tick.symbol)
        if cur is None or cur.ts != minute:
            done = cur
            self._current[tick.symbol] = Candle(tick.symbol, minute, tick.price, tick.price, tick.price, tick.price, tick.qty)
            if done is not None:
                arr = self.candles.setdefault(tick.symbol, deque(maxlen=self.maxlen))
                arr.append(done)
                return done
            return None
        cur.high = max(cur.high, tick.price)
        cur.low = min(cur.low, tick.price)
        cur.close = tick.price
        cur.volume += tick.qty
        return None
