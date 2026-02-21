from __future__ import annotations

import json
import sqlite3
from threading import RLock
from datetime import datetime, timedelta, timezone
from pathlib import Path

from danbot.strategy.signals import StrategySignal


class Database:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = RLock()

    def init(self, schema_path: Path | str) -> None:
        schema = Path(schema_path).read_text()
        with self._lock:
            self.conn.executescript(schema)
            self.conn.commit()

    def insert_signal(self, ts: str, signal: StrategySignal) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO signals(ts,symbol,state,confidence,side,reasons,features_json) VALUES(?,?,?,?,?,?,?)",
                (
                    ts,
                    signal.symbol,
                    signal.state.value,
                    signal.confidence,
                    signal.side,
                    ",".join(signal.reason_codes),
                    json.dumps(signal.features),
                ),
            )
            self.conn.commit()

    def insert_trade(self, ts: str, symbol: str, side: str, qty: float, price: float, fee: float, pnl: float, slippage_bps: float) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO trades(ts,symbol,side,qty,price,fee,pnl,slippage_bps) VALUES(?,?,?,?,?,?,?,?)",
                (ts, symbol, side, qty, price, fee, pnl, slippage_bps),
            )
            self.conn.commit()

    def insert_incident(self, ts: str, level: str, message: str, details: str = "") -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO incidents(ts,level,message,details) VALUES(?,?,?,?)",
                (ts, level, message, details),
            )
            self.conn.commit()

    def insert_lifelog(
        self,
        ts: str,
        severity: str,
        category: str,
        message: str,
        symbol: str = "",
        reason_codes: list[str] | None = None,
        metrics: dict | None = None,
    ) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO lifelog(ts,severity,category,symbol,message,reason_codes,json_metrics) VALUES(?,?,?,?,?,?,?)",
                (ts, severity, category, symbol, message, ",".join(reason_codes or []), json.dumps(metrics or {})),
            )
            self.conn.commit()

    def list_recent_lifelog(self, limit: int = 2000) -> list[sqlite3.Row]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT ts,severity,category,symbol,message,json_metrics FROM lifelog ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return list(reversed(rows))

    def insert_health_metric(self, ts: str, latency_ms: float, stale_flag: bool, positions_count: int, daily_loss_pct: float) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO health_metrics(ts,latency_ms,stale_flag,positions_count,daily_loss_pct) VALUES(?,?,?,?,?)",
                (ts, latency_ms, 1 if stale_flag else 0, positions_count, daily_loss_pct),
            )
            self.conn.commit()

    def closed_trade_metrics_24h(self) -> dict[str, float | None]:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        with self._lock:
            rows = self.conn.execute(
                "SELECT ts, pnl FROM trades WHERE ts >= ? ORDER BY ts ASC",
                (since,),
            ).fetchall()
        if not rows:
            return {"winrate": None, "profit": None, "drawdown": None, "closed_count": 0}
        pnls = [float(r["pnl"] or 0.0) for r in rows]
        wins = sum(1 for p in pnls if p > 0)
        total = len(pnls)
        profit = sum(pnls)
        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        for p in pnls:
            equity += p
            peak = max(peak, equity)
            max_dd = max(max_dd, peak - equity)
        return {
            "winrate": (wins / total) * 100.0,
            "profit": profit,
            "drawdown": max_dd,
            "closed_count": total,
        }
