from __future__ import annotations

from collections import deque
from statistics import mean, pstdev


def zscore(value: float, history: deque[float]) -> float:
    if len(history) < 2:
        return 0.0
    m = mean(history)
    sd = pstdev(history)
    return 0.0 if sd == 0 else (value - m) / sd
