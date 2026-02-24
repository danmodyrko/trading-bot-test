from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

import aiohttp
from aiohttp import ClientResponseError

from danbot.core.logging import get_logger, safe_json


class BinanceRestClient:
    def __init__(self, base_url: str, api_key: str = "", api_secret: str = "", recv_window: int = 10000) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.recv_window = recv_window
        self.time_offset_ms = 0
        self._log = get_logger(__name__)

    def _sign(self, params: dict[str, Any]) -> str:
        query = urlencode(params)
        return hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()

    def set_time_offset(self, offset_ms: int) -> None:
        self.time_offset_ms = int(offset_ms)

    def _signed_params(self, params: dict[str, Any]) -> dict[str, Any]:
        payload = {k: v for k, v in params.items() if k != "signature"}
        payload["timestamp"] = int(time.time() * 1000) + self.time_offset_ms
        payload["recvWindow"] = int(payload.get("recvWindow", self.recv_window))
        payload["signature"] = self._sign(payload)
        return payload

    async def get(self, path: str, params: dict[str, Any] | None = None, signed: bool = False) -> Any:
        raw_params = params or {}
        params = dict(raw_params)
        if signed:
            params = self._signed_params(raw_params)
        headers = {"X-MBX-APIKEY": self.api_key} if self.api_key else {}
        self._log.debug("REST request %s", safe_json({"path": path, "signed": signed, "params": params}))

        async def _call() -> Any:
            async with aiohttp.ClientSession(base_url=self.base_url, headers=headers) as session:
                async with session.get(path, params=params, timeout=10) as resp:
                    payload = await resp.text()
                    if resp.status >= 400:
                        detail = payload
                        try:
                            parsed = await resp.json(content_type=None)
                            if isinstance(parsed, dict):
                                code = parsed.get("code")
                                msg = parsed.get("msg")
                                detail = f"code={code}, msg={msg}" if code is not None or msg is not None else str(parsed)
                        except Exception:
                            pass
                        self._log.warning("REST error %s", safe_json({"path": path, "status": resp.status, "detail": detail}))
                        raise ClientResponseError(
                            resp.request_info,
                            tuple(resp.history),
                            status=resp.status,
                            message=detail,
                            headers=resp.headers,
                        )
                    return await resp.json(content_type=None)

        return await _call()

    async def post(self, path: str, params: dict[str, Any] | None = None, signed: bool = False) -> Any:
        raw_params = params or {}
        payload = dict(raw_params)
        if signed:
            payload = self._signed_params(raw_params)
        headers = {"X-MBX-APIKEY": self.api_key} if self.api_key else {}
        self._log.debug("REST post %s", safe_json({"path": path, "signed": signed, "params": payload}))

        async def _call() -> Any:
            async with aiohttp.ClientSession(base_url=self.base_url, headers=headers) as session:
                async with session.post(path, data=payload, timeout=10) as resp:
                    body = await resp.text()
                    if resp.status >= 400:
                        detail = body
                        try:
                            parsed = await resp.json(content_type=None)
                            if isinstance(parsed, dict):
                                code = parsed.get("code")
                                msg = parsed.get("msg")
                                detail = f"code={code}, msg={msg}" if code is not None or msg is not None else str(parsed)
                        except Exception:
                            pass
                        raise ClientResponseError(resp.request_info, tuple(resp.history), status=resp.status, message=detail, headers=resp.headers)
                    return await resp.json(content_type=None)

        return await _call()
