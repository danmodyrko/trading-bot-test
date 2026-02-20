from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(slots=True)
class Tick:
    symbol: str
    price: float
    qty: float
    ts: datetime


@dataclass(slots=True)
class OrderRequest:
    symbol: str
    side: Side
    qty: float
    reduce_only: bool = False


@dataclass(slots=True)
class Fill:
    symbol: str
    side: Side
    qty: float
    price: float
    fee: float
    ts: datetime
    order_id: str = ""


@dataclass(slots=True)
class Position:
    symbol: str
    qty: float = 0.0
    entry_price: float = 0.0
    unrealized_pnl: float = 0.0
    updated_at: datetime | None = None


@dataclass(slots=True)
class AccountSnapshot:
    equity: float
    free_balance: float
    ts: datetime
    positions: dict[str, Position] = field(default_factory=dict)
