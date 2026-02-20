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
