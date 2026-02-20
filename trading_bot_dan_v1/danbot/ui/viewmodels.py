from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SymbolCardVM:
    symbol: str
    price: float = 0.0
    state: str = "BUILDUP"
    confidence: float = 0.0
    pnl: float = 0.0


@dataclass
class AppVM:
    mode: str
    connected: bool = False
    latency_ms: int = 0
    cards: dict[str, SymbolCardVM] = field(default_factory=dict)
