# Trading Bot Dan v1

Dan v1 now uses a two-tab dashboard:
- **Live Log** (dominant)
- **Settings**

Bottom metrics are always visible: Win Rate 24h, Drawdown 24h, Profit 24h, Uptime, Current Balance.

## Run (Windows)
```bat
run.bat
```

## Run (Linux/macOS)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m danbot.main
```

## DEMO vs REAL data source
- **DEMO** mode uses Binance Futures **Testnet** signed account endpoints.
- **REAL** mode uses Binance Futures **Live** signed account endpoints.
- If keys are missing, UI shows **NOT CONFIGURED** and trading remains blocked.

## API setup
1. Copy `.env.example` to `.env`.
2. Fill testnet/live credentials.
3. Open **Settings** tab and click test connection.

## REAL safety
REAL mode requires gate confirmation in Settings before START:
- type `REAL`
- check acknowledgement
- DRY RUN stays ON by default.

## Persistence
- Runtime settings: `data/app_state.json`
- Logs/trades: `data/danbot.sqlite3`
