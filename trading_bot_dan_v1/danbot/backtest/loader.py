from __future__ import annotations

import csv
from pathlib import Path

from danbot.data.candles import Candle
from datetime import datetime


def load_klines_csv(path: Path, symbol: str) -> list[Candle]:
    out: list[Candle] = []
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            out.append(
                Candle(
                    symbol=symbol,
                    ts=datetime.fromisoformat(row["ts"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )
            )
    return out
