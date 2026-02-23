# RUN GUIDE

## One-command production run (Windows)
Run:

```bat
scripts\run_prod.bat
```

This single command does all of the following:
- creates `.venv` if missing,
- installs Python dependencies,
- optionally builds frontend assets if `web/dist` is missing and `npm` is available,
- starts FastAPI (`uvicorn api.main:app --host 127.0.0.1 --port 8000`),
- opens your browser to `http://127.0.0.1:8000`.

## Behavior when npm / Node.js is missing
If `web/dist` is missing and npm is not installed, startup is still successful for backend + engine API.

You will see this clear message:

```text
Node.js/npm not installed.
Backend started without UI.
Install Node.js LTS to enable dashboard.
```

Install Node.js LTS from: https://nodejs.org/

## Development mode (Windows)
Run:

```bat
scripts\dev.bat
```

Behavior:
- starts backend with reload,
- starts Vite dev server when npm exists,
- skips Vite and prints warning when npm is missing,
- prints API/UI/WebSocket URLs.

## Engine safety defaults
- Engine controller initializes on backend startup.
- Engine starts **IDLE** by default (`running=false`).
- Trading is **not** started automatically.
- Manual Start action from the dashboard/API is required.

## Ports used
- `127.0.0.1:8000` → FastAPI backend, `/api/*`, `/ws/events`, and production UI (when built).
- `127.0.0.1:5173` → Vite dev server (dev mode only).

## Realtime WebSocket updates
WebSocket endpoint:

```text
ws://127.0.0.1:8000/ws/events
```

Authentication:
- pass token query string: `?token=<APP_API_TOKEN>`.

Event flow after connect:
1. server sends an initial `snapshot` payload,
2. server streams `event` updates from the engine event bus,
3. server streams periodic `status` updates,
4. server sends heartbeat `ping`; client can respond with `{ "type": "pong" }`.

## Smoke test
After server is running, verify API + websocket quickly:

```bat
python scripts\smoke_test.py
```

It will:
- call `/api/status`,
- connect to `/ws/events`,
- print the first received websocket message.
