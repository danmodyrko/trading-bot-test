from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SymbolCardVM:
    symbol: str
    price: float = 0.0
    state: str = "BUILDUP"
    confidence: float = 0.0
    pnl: float = 0.0
    impulse_score: float = 0.0
    exhaustion_ratio: float = 1.0
    classifier_label: str = "-"
    classifier_confidence: float = 0.0
    expected_slippage_bps: float = 0.0
    spread_bps: float = 0.0
    vol_10s: float = 0.0
    regime_status: str = "MEAN_REVERSION"
    decision: str = "WAIT"


@dataclass
class LogEntryVM:
    ts: str
    severity: str
    category: str
    symbol: str
    message: str


@dataclass
class AppVM:
    mode: str
    dry_run: bool = True
    connected: bool = False
    latency_ms: int = 0
    cards: dict[str, SymbolCardVM] = field(default_factory=dict)
    logs: list[LogEntryVM] = field(default_factory=list)
