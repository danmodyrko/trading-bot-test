from __future__ import annotations

import os

from fastapi import Header, HTTPException, WebSocket


def get_api_token() -> str:
    return os.getenv("APP_API_TOKEN", "dev-token")


def require_rest_token(x_api_token: str | None = Header(default=None)) -> None:
    if not x_api_token:
        raise HTTPException(status_code=401, detail="missing api token")
    if x_api_token != get_api_token():
        raise HTTPException(status_code=401, detail="invalid api token")


async def require_ws_token(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=1008, reason="missing token")
        raise RuntimeError("missing token")
    if token != get_api_token():
        await websocket.close(code=1008, reason="invalid token")
        raise RuntimeError("invalid token")
