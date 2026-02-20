from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

import aiohttp


class BinanceRestClient:
    def __init__(self, base_url: str, api_key: str = "", api_secret: str = "") -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.api_secret = api_secret

    def _sign(self, params: dict[str, Any]) -> str:
        query = urlencode(params)
        return hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()

    async def get(self, path: str, params: dict[str, Any] | None = None, signed: bool = False) -> dict[str, Any]:
        params = params or {}
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["signature"] = self._sign(params)
        headers = {"X-MBX-APIKEY": self.api_key} if self.api_key else {}
        async with aiohttp.ClientSession(base_url=self.base_url, headers=headers) as session:
            async with session.get(path, params=params, timeout=10) as resp:
                resp.raise_for_status()
                return await resp.json()
