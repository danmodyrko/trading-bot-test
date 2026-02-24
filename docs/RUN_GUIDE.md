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

## 2) Development
```bat
scripts\dev.bat
```
- Starts API with reload on `http://127.0.0.1:8000`.
- Starts Vite on `http://127.0.0.1:5173` when npm exists.

## 3) Required token header
All REST requests require:
- Header `X-API-TOKEN: <APP_API_TOKEN>`

WebSocket requires:
- `ws://127.0.0.1:8000/ws/events?token=<APP_API_TOKEN>`

## 4) Smoke test
After server is running:
```bat
python scripts\smoke_test.py
```
It checks `/api/status`, `/api/settings`, `/api/positions`, and websocket first event.
