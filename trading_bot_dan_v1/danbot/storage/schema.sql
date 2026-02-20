CREATE TABLE IF NOT EXISTS candles_1m (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  symbol TEXT NOT NULL,
  open REAL,
  high REAL,
  low REAL,
  close REAL,
  volume REAL
);

CREATE TABLE IF NOT EXISTS signals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  symbol TEXT NOT NULL,
  state TEXT NOT NULL,
  confidence REAL,
  side TEXT,
  reasons TEXT,
  features_json TEXT
);

CREATE TABLE IF NOT EXISTS trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  qty REAL,
  price REAL,
  fee REAL,
  pnl REAL,
  slippage_bps REAL
);

CREATE TABLE IF NOT EXISTS incidents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  level TEXT NOT NULL,
  message TEXT NOT NULL,
  details TEXT
);

CREATE TABLE IF NOT EXISTS lifelog (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  severity TEXT NOT NULL,
  category TEXT NOT NULL,
  symbol TEXT,
  message TEXT NOT NULL,
  reason_codes TEXT,
  json_metrics TEXT
);

CREATE TABLE IF NOT EXISTS health_metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  latency_ms REAL,
  stale_flag INTEGER,
  positions_count INTEGER,
  daily_loss_pct REAL
);
