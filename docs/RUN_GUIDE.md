# Run Guide

## Prerequisites
- Python 3.11+
- Node.js 20+
- Windows Command Prompt (for the provided `.bat` scripts)

---

## Single-command runtime requirement
Both of these commands start the FastAPI server and attach the `EngineController`:

```bat
python run.py
```

or

```bat
python -m api
```

Behavior:
- API endpoints are available under `/api/*`.
- Event websocket is available at `/ws/events`.
- If `web/dist` exists, the built UI is served at `/` and static assets under `/assets/*`.
- Engine controller is attached at startup.
- Engine trading loop **does not auto-start** unless `APP_AUTOSTART=true` is set.

---

## Development mode (Vite + backend reload)
Use:

```bat
scripts\dev.bat
```

What it does:
- sets `APP_ENV=dev` so backend enables CORS for the Vite dev server.
- starts backend with reload:
  - `uvicorn api.main:app --reload --host 127.0.0.1 --port 8000`
- starts frontend Vite dev server on `http://127.0.0.1:5173`
- prints backend/frontend URLs in the terminal.

### Dev URLs
- Backend API: `http://127.0.0.1:8000/api/...`
- WebSocket: `ws://127.0.0.1:8000/ws/events`
- Frontend (Vite): `http://127.0.0.1:5173`

---

## Production mode (backend serves built UI)
Use:

```bat
scripts\run_prod.bat
```

What it does:
1. Runs frontend dependency install/build:
   - `npm ci`
   - `npm run build`
2. Starts backend only via:
   - `python run.py`
3. Backend serves built frontend from `web/dist`:
   - `GET /` -> `index.html`
   - static assets at `/assets/*`
   - client-side routes fallback to `index.html`

### Production URL
- UI + API: `http://127.0.0.1:8000`

---

## Optional environment variables
- `APP_API_TOKEN` – API/WS bearer token.
- `APP_ENV` – `dev` to enable CORS for Vite; defaults to `prod` behavior.
- `APP_AUTOSTART` – set to `true`/`1`/`yes`/`on` to auto-start engine loop at server startup.
- `APP_HOST` – host for `run.py` / `python -m api` (default `127.0.0.1`).
- `APP_PORT` – port for `run.py` / `python -m api` (default `8000`).
