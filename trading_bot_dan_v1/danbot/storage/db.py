from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from danbot.strategy.signals import StrategySignal


class Database:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)

    def init(self, schema_path: Path | str) -> None:
        schema = Path(schema_path).read_text()
        self.conn.executescript(schema)
        self.conn.commit()

    def insert_signal(self, ts: str, signal: StrategySignal) -> None:
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

    def insert_incident(self, ts: str, level: str, message: str, details: str = "") -> None:
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
        self.conn.execute(
            "INSERT INTO lifelog(ts,severity,category,symbol,message,reason_codes,json_metrics) VALUES(?,?,?,?,?,?,?)",
            (ts, severity, category, symbol, message, ",".join(reason_codes or []), json.dumps(metrics or {})),
        )
        self.conn.commit()

    def insert_health_metric(self, ts: str, latency_ms: float, stale_flag: bool, positions_count: int, daily_loss_pct: float) -> None:
        self.conn.execute(
            "INSERT INTO health_metrics(ts,latency_ms,stale_flag,positions_count,daily_loss_pct) VALUES(?,?,?,?,?)",
            (ts, latency_ms, 1 if stale_flag else 0, positions_count, daily_loss_pct),
        )
        self.conn.commit()
