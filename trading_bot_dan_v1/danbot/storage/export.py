from __future__ import annotations

import csv
import sqlite3
from pathlib import Path


def export_table(db_path: Path, table: str, output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.execute(f"SELECT * FROM {table}")
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([d[0] for d in cur.description])
        writer.writerows(cur.fetchall())
    conn.close()
