# Trading Bot Dan v1

Binance USDT-M futures scalper with tick-domain impulse/exhaustion detection, probabilistic state machine, dynamic symbol discovery, LiveLog, and safety circuit breakers.

## Quick start (Windows)
```bat
run.bat
```

## Quick start (Linux/macOS)
```bash
./run.sh
```

## Windows `uv` not recognized?
If `run.bat` shows `"uv" is not recognized`, it now falls back to `python -m uv` automatically after installation.
You can also run manually:
```bat
python -m uv sync
python -m uv run python -m danbot.main
```

## UV direct commands
```bash
uv sync
uv run python -m danbot.main
uv run python -m danbot.main --headless
```

## Modes
- **DEMO**: paper simulator path works without API keys.
- **REAL**: requires typing `REAL`, checking acknowledgement, and 10-second countdown in UI.
- **DRY-RUN**: default ON. Even in REAL, no orders are sent unless explicitly enabled.

## API keys
Create `.env` and set your keys if you want exchange execution:
```env
BINANCE_API_KEY=...
BINANCE_API_SECRET=...
```

## Dynamic symbol discovery
At startup the bot queries Binance `exchangeInfo` + `ticker/24hr`, includes all USDT perpetual symbols in TRADING state passing liquidity filters, and enforces `max_symbols_active` (default 100). Remaining symbols are watch-only.

## Safety guards
- Global kill switch (`Ctrl+K`)
- Daily loss, max positions, staleness, volatility, spread and slippage guards
- Cost-vs-edge rejection using expected slippage model
- Regime filter ON by default (reversal disabled in trend regime)

## Troubleshooting websockets
- If stream heartbeat is stale the bot blocks new entries and logs incidents.
- Connectivity issues automatically trigger reconnect with backoff.
- In environments without Binance access, use `--headless` demo/paper simulation.

## Optional Windows EXE build
```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows_exe.ps1
```
