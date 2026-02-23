from __future__ import annotations

import csv
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, sort_keys=True, indent=2)
        tmp.flush()
        temp_path = Path(tmp.name)
    temp_path.replace(path)


@dataclass
class SnapshotStore:
    path: Path

    def save(self, snapshot: dict[str, Any]) -> None:
        atomic_write_json(self.path, snapshot)


@dataclass
class TradeJournal:
    path: Path

    def append_completed_trade(self, row: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        exists = self.path.exists()
        fieldnames = [
            "entry_time",
            "exit_time",
            "symbol",
            "side",
            "size",
            "entry_price",
            "exit_price",
            "fees",
            "pnl",
            "mfe",
            "mae",
            "slippage",
            "reason",
            "model_score",
            "correlation_id",
        ]
        with self.path.open("a", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=fieldnames)
            if not exists:
                writer.writeheader()
            out = {name: row.get(name, "") for name in fieldnames}
            writer.writerow(out)
