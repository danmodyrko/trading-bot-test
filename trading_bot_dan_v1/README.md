# Trading Bot Dan v1

Production-style Binance Futures impulse lifecycle scalper with desktop UI, journaling, backtest, and paper/real execution safety gates.

## Features
- Event-driven strategy lifecycle: `BUILDUP → IMPULSE → CLIMAX → EXHAUSTION → REBALANCE`
- Entry only during exhaustion + first structure confirmation.
- DEMO vs REAL separation with persistent mode badge and REAL confirmation gate.
- Risk controls: daily loss circuit breaker, position cap, slippage/spread/depth guards, dry-run mode.
- SQLite journaling for signals/trades/incidents + CSV export utility.
- Backtest/replay modules for strategy validation.

## Installation
```bash
cd trading_bot_dan_v1
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .[dev]
cp .env.example .env
```

## Run UI
```bash
python -m danbot.main
```

## Run headless
```bash
python -m danbot.main --headless
```

## DEMO vs REAL
- `mode = "DEMO"` routes to testnet-compatible endpoints and supports paper simulation.
- `mode = "REAL"` uses live endpoints and should only be enabled after UI confirmation (type `REAL`, check acknowledgement, 10 second arming countdown).
- Keep `execution.dry_run = true` until fully validated.

## Config
All runtime controls are in `config.toml`: symbols, websocket/rest endpoints, risk, strategy, execution, UI refresh, and storage paths.
Secrets (`BINANCE_API_KEY`, `BINANCE_API_SECRET`) must be provided via environment variables.

## Troubleshooting (Windows-first)
- If PySide6 fails, install latest Visual C++ runtime and retry pip install.
- If websocket disconnects frequently, check firewall/proxy and lower symbol count.
- Bot blocks new trades when feed is stale and logs incident records.

## Disclaimer
Not financial advice. You are solely responsible for all trading decisions and losses. Validate in DEMO/paper mode first.
