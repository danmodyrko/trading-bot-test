# V2 Architecture

## Step 0: V1 feature mapping to V2

| V1 desktop feature | V2 route/component | API endpoint/event |
|---|---|---|
| START / STOP buttons | Operator Actions rail + top bar | `POST /api/start`, `POST /api/stop`, `SYSTEM` events |
| Pause entries | Operator Actions rail | `POST /api/pause`, `POST /api/resume`, `RISK` events |
| Flatten / kill switch | Operator Actions rail | `POST /api/flatten`, `POST /api/kill` |
| Mode DEMO/REAL | Top KPI bar mode toggle | `PUT /api/settings` (`mode`) |
| Connection test | Settings page control | `POST /api/test-connection` |
| Runtime settings edits | Settings page form | `GET/PUT /api/settings` |
| Live log panel | Terminal Feed card with filters | `WS /ws/events` categories |
| Positions/orders panels | Center tables + dedicated pages | `GET /api/positions`, `GET /api/orders` |
| Recent signals panel | Signals card | `GET /api/signals`, `SIGNAL` events |
| Journal/history | Journal page + table | `GET /api/journal` |

## Module boundaries

- `/engine`
  - Pure headless domain behavior.
  - Owns lifecycle state (running/stopped, pause, kill), settings persistence, simulated execution loop, and in-memory event bus.
  - No frontend imports.
- `/api`
  - FastAPI interface layer.
  - Auth checks (`X-API-TOKEN` for REST, query token for WS), route mapping, WS fanout.
- `/web`
  - React/Vite/Tailwind client-only dashboard.
  - Bootstraps initial REST snapshot and then applies WS stream updates.
- `/scripts`
  - Windows DX launch scripts and smoke test.
- `/docs`
  - Architecture, API contract, runbook, verification checklist.

## Data flow

1. UI calls REST snapshot endpoints for initial state.
2. UI connects to WS with token.
3. API sends initial snapshot envelope (`status`, `settings`, `positions`, `orders`, recent events).
4. Engine loop emits categorized events (`SIGNAL`, `ORDER`, `FILL`, etc.).
5. API forwards events + 1s status ticks + heartbeat pings.
6. UI renders terminal feed/tables in real time and sends operator commands via REST.

## Reliability model

- WS heartbeat ping/pong every 10s.
- Server queue maxsize limits per client; oldest messages are compacted when slow clients back up.
- Client reconnect uses exponential backoff and shows disconnected banner.
