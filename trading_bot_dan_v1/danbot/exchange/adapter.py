from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from danbot.core.config import Mode
from danbot.exchange.binance_endpoints import LIVE_REST, TESTNET_REST
from danbot.exchange.rest_client import BinanceRestClient


@dataclass(slots=True)
class ExchangeAdapter:
    mode: Mode
    api_key: str
    api_secret: str

    def __post_init__(self) -> None:
        base_url = TESTNET_REST if self.mode == Mode.DEMO else LIVE_REST
        self.client = BinanceRestClient(base_url=base_url, api_key=self.api_key, api_secret=self.api_secret)

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    async def ping_latency_ms(self) -> float:
        start = time.perf_counter()
        await self.client.get("/fapi/v1/ping")
        return (time.perf_counter() - start) * 1000

    async def get_account_overview(self) -> dict[str, float | int]:
        if not self.configured:
            raise RuntimeError("NOT CONFIGURED")
        data = await self.client.get("/fapi/v2/account", signed=True)
        assets = {item.get("asset"): item for item in data.get("assets", [])}
        usdt = assets.get("USDT", {})
        return {
            "balance_usdt": float(usdt.get("walletBalance", 0.0)),
            "available_usdt": float(usdt.get("availableBalance", 0.0)),
            "unrealized_pnl": float(usdt.get("unrealizedProfit", 0.0)),
            "margin_used": float(data.get("totalInitialMargin", 0.0)),
            "timestamp": int(time.time() * 1000),
        }

    async def get_positions(self) -> list[dict[str, Any]]:
        if not self.configured:
            return []
        account = await self.client.get("/fapi/v2/account", signed=True)
        out: list[dict[str, Any]] = []
        for pos in account.get("positions", []):
            qty = float(pos.get("positionAmt", 0.0))
            if abs(qty) <= 0:
                continue
            out.append(pos)
        return out

    async def get_recent_fills(self, limit: int = 100, since_ts: int | None = None) -> list[dict[str, Any]]:
        if not self.configured:
            return []
        params: dict[str, Any] = {"limit": max(1, min(limit, 1000))}
        if since_ts:
            params["startTime"] = since_ts
        fills = await self.client.get("/fapi/v1/userTrades", params=params, signed=True)
        return fills if isinstance(fills, list) else []

    async def get_income_history(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.configured:
            return []
        payload = await self.client.get("/fapi/v1/income", params={"limit": max(1, min(limit, 1000))}, signed=True)
        return payload if isinstance(payload, list) else []
