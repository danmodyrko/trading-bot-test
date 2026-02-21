from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

import aiohttp
from aiohttp import ClientResponseError


class BinanceRestClient:
    def __init__(self, base_url: str, api_key: str = "", api_secret: str = "") -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.api_secret = api_secret

    def _sign(self, params: dict[str, Any]) -> str:
        query = urlencode(params)
        return hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()

    async def get(self, path: str, params: dict[str, Any] | None = None, signed: bool = False) -> Any:
        params = params or {}
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["signature"] = self._sign(params)
        headers = {"X-MBX-APIKEY": self.api_key} if self.api_key else {}
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
                    raise ClientResponseError(
                        resp.request_info,
                        tuple(resp.history),
                        status=resp.status,
                        message=detail,
                        headers=resp.headers,
                    )
                return await resp.json(content_type=None)
