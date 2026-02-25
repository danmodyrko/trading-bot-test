# Run Guide (Windows)

## 1) Production one-command
```bat
scripts\run_prod.bat
```
What it does:
- Creates `.venv` if missing.
- Installs Python dependencies.
- If npm exists: installs frontend deps + builds `web/dist`.
- If npm does not exist: prints a clear warning and starts backend only.
- Uses `APP_API_TOKEN` for auth (set it before running for non-default).
- Starts `uvicorn api.main:app --host 127.0.0.1 --port 8000`.

## 2) Development (backend + frontend)
```bat
scripts\dev.bat
```
- Starts API with reload on `http://127.0.0.1:8000`.
- Starts Vite on `http://127.0.0.1:5173`.

## 3) Environment variables
Set these before start if you want env-based credentials fallback:
```bat
set APP_API_TOKEN=dev-token
set BINANCE_TESTNET_API_KEY=...
set BINANCE_TESTNET_API_SECRET=...
set BINANCE_API_KEY=...
set BINANCE_API_SECRET=...
```

## 4) Runtime persistence locations
- Main settings: `trading_bot_dan_v1/config.toml`
- App state: `trading_bot_dan_v1/data/app_state.json`
- API credentials written from Config page: `trading_bot_dan_v1/data/api_credentials.json`
- SQLite logs/history: `trading_bot_dan_v1/data/danbot.sqlite3`

## 5) Required auth
All REST requests require header:
- `X-API-TOKEN: <APP_API_TOKEN>`

WebSocket requires:
- `ws://127.0.0.1:8000/ws/events?token=<APP_API_TOKEN>`

## 6) Smoke test
After server is running:
```bat
python scripts\smoke_test.py
```

## 7) Visual regression screenshots
```bat
cd web
npm run test:visual
```
(Make sure frontend dev server is running first.)
