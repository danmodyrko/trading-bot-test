from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass(slots=True)
class DashboardState:
    mode: str = "DEMO"
    dry_run: bool = True
    ws_latency_ms: float = 0.0
    risk_pct: float = 1.0
    bot_uptime_seconds: int = 0
    current_balance_usdt: float | None = None
    metrics_24h_winrate: float | None = None
    metrics_24h_drawdown: float | None = None
    metrics_24h_profit: float | None = None
    api_configured: bool = False


@dataclass(slots=True)
class LiveLogEntry:
    ts_iso: str
    severity: str
    category: str
    symbol: str | None
    message: str
    metrics: dict[str, float] = field(default_factory=dict)


class LiveLogModel:
    def __init__(self, max_entries: int = 2000) -> None:
        self._entries: deque[LiveLogEntry] = deque(maxlen=max_entries)

    def append(self, entry: LiveLogEntry) -> None:
        self._entries.append(entry)

    def get_filtered(self, severity: str = "ALL", search_text: str = "") -> list[LiveLogEntry]:
        severity_upper = severity.upper().strip()
        search = search_text.lower().strip()
        out: list[LiveLogEntry] = []
        for e in self._entries:
            if severity_upper != "ALL" and e.severity.upper() != severity_upper:
                continue
            haystack = f"{e.category} {e.symbol or ''} {e.message}".lower()
            if search and search not in haystack:
                continue
            out.append(e)
        return out

    @property
    def entries(self) -> list[LiveLogEntry]:
        return list(self._entries)
