# API Spec (V2)

Auth:
- REST: header `X-API-TOKEN: <token>` required on all `/api/*` routes.
- WS: `GET /ws/events?token=<token>`.

## REST

- `POST /api/start`
- `POST /api/stop`
- `POST /api/pause`
- `POST /api/resume`
- `POST /api/flatten`
- `POST /api/kill`
- `GET /api/status`
- `GET /api/settings`
- `PUT /api/settings` (JSON partial settings patch)
- `POST /api/test-connection` body: `{ "mode": "DEMO" | "REAL" }`
- `GET /api/positions`
- `GET /api/orders`
- `GET /api/signals`
- `GET /api/journal?page=1&page_size=50`

## WebSocket

`WS /ws/events?token=...`

### Message types from server

1. Initial snapshot:
```json
{
  "type": "snapshot",
  "status": {"running": false, "mode": "DEMO"},
  "settings": {},
  "positions": [],
  "orders": [],
  "events": []
}
```

2. Event stream:
```json
{
  "type": "event",
  "event": {
    "ts": "2026-01-01T00:00:00+00:00",
    "level": "INFO",
    "category": "ORDER",
    "message": "Order FILLED BTCUSDT",
    "symbol": "BTCUSDT",
    "correlation_id": "...",
    "payload": {}
  }
}
```

3. Periodic status tick (1s):
```json
{ "type": "status", "status": {"running": true, "uptime_seconds": 12} }
```

4. Heartbeat:
```json
{ "type": "ping" }
```

### Client message

```json
{ "type": "pong" }
```

## Event categories

`WS, SIGNAL, FILTER, ORDER, FILL, POSITION, RISK, SYSTEM, ERROR`
