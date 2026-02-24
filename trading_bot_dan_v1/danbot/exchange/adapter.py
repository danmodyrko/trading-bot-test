from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from aiohttp import ClientResponseError

from danbot.core.config import Mode
from danbot.core.events import EventRecord, get_event_bus
from danbot.core.logging import get_logger, mask_api_key, safe_json
from danbot.exchange.binance_endpoints import LIVE_REST, TESTNET_REST
from danbot.exchange.rest_client import BinanceRestClient


class NotConfiguredError(RuntimeError):
    pass


@dataclass(slots=True)
class TimeSync:
    demo_offset_ms: int = 0
    real_offset_ms: int = 0

    @property
    def offset_ms(self) -> int:
        return self.demo_offset_ms

    def set_offset(self, mode: Mode, offset_ms: int) -> None:
        if mode == Mode.DEMO:
            self.demo_offset_ms = int(offset_ms)
        else:
            self.real_offset_ms = int(offset_ms)

    def get_offset(self, mode: Mode) -> int:
        return self.demo_offset_ms if mode == Mode.DEMO else self.real_offset_ms


@dataclass(slots=True)
class ExchangeAdapter:
    mode: Mode
    api_key: str
    api_secret: str
    time_sync: TimeSync | None = None
    client: BinanceRestClient = field(init=False)
    _log: Any = field(init=False, repr=False)
    _events: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        base_url = TESTNET_REST if self.mode == Mode.DEMO else LIVE_REST
        self.client = BinanceRestClient(base_url=base_url, api_key=self.api_key, api_secret=self.api_secret)
        if self.time_sync is None:
            self.time_sync = TimeSync()
        self._log = get_logger(__name__)
        self._events = get_event_bus()
        self._log.info("ExchangeAdapter init %s", safe_json({"mode": self.mode.value, "api_key": mask_api_key(self.api_key)}))

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def _require_keys(self) -> None:
        if not self.api_key or not self.api_secret:
            self._events.incident("API_ERROR", "API NOT CONFIGURED", details={"mode": self.mode.value})
            raise NotConfiguredError("API NOT CONFIGURED")

    def switch_mode(self, mode: Mode) -> None:
        self.mode = mode
        self.client.base_url = TESTNET_REST if self.mode == Mode.DEMO else LIVE_REST
        self._log.info("switch_mode %s", safe_json({"mode": self.mode.value}))

    async def sync_time(self) -> int:
        try:
            server = await self.client.get("/fapi/v1/time", signed=False)
            server_time = int(server.get("serverTime", int(time.time() * 1000)))
            local_time = int(time.time() * 1000)
            offset = server_time - local_time
            self.time_sync.set_offset(self.mode, offset)
            self.client.set_time_offset(offset)
            self._events.publish(EventRecord(action="TIME_SYNC", message="time sync success", details={"mode": self.mode.value, "offset_ms": offset}))
            return offset
        except Exception as exc:
            self._events.incident("API_ERROR", f"time sync failed: {exc}", details={"mode": self.mode.value})
            raise

    async def ensure_mode(self, mode: Mode) -> None:
        if mode != self.mode:
            self.switch_mode(mode)
        self.client.set_time_offset(self.time_sync.get_offset(self.mode))
        await self.sync_time()

    async def ping_latency_ms(self) -> float:
        start = time.perf_counter()
        await self.client.get("/fapi/v1/ping")
        latency = (time.perf_counter() - start) * 1000
        self._log.debug("ping_latency_ms %s", safe_json({"latency_ms": round(latency, 2), "mode": self.mode.value}))
        return latency

    async def _signed_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self._require_keys()
        offset = self.time_sync.get_offset(self.mode)
        self.client.set_time_offset(offset)
        if offset == 0:
            await self.sync_time()
            self.client.set_time_offset(self.time_sync.get_offset(self.mode))
        try:
            return await self.client.get(path, params=params, signed=True)
        except ClientResponseError as exc:
            if self._is_time_sync_error(exc):
                self._events.publish(EventRecord(action="API_RETRY", message="request retry after time sync", category="INFO", details={"path": path, "mode": self.mode.value}))
                await self.sync_time()
                self.client.set_time_offset(self.time_sync.get_offset(self.mode))
                return await self.client.get(path, params=params, signed=True)
            self._events.incident("API_ERROR", f"signed request failed: {exc}", details={"path": path, "mode": self.mode.value})
            raise

    async def _signed_post(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self._require_keys()
        offset = self.time_sync.get_offset(self.mode)
        self.client.set_time_offset(offset)
        if offset == 0:
            await self.sync_time()
            self.client.set_time_offset(self.time_sync.get_offset(self.mode))
        try:
            return await self.client.post(path, params=params, signed=True)
        except ClientResponseError as exc:
            if self._is_time_sync_error(exc):
                self._events.publish(EventRecord(action="API_RETRY", message="request retry after time sync", category="INFO", details={"path": path, "mode": self.mode.value}))
                await self.sync_time()
                self.client.set_time_offset(self.time_sync.get_offset(self.mode))
                return await self.client.post(path, params=params, signed=True)
            self._events.incident("API_ERROR", f"signed request failed: {exc}", details={"path": path, "mode": self.mode.value})
            raise

    def _is_time_sync_error(self, exc: ClientResponseError) -> bool:
        if "code=-1021" in exc.message:
            return True
        try:
            payload = json.loads(exc.message)
        except Exception:
            return False
        return isinstance(payload, dict) and int(payload.get("code", 0)) == -1021

    async def get_account_overview(self) -> dict[str, float | int]:
        data = await self._signed_get("/fapi/v2/account")
        assets = {item.get("asset"): item for item in data.get("assets", [])}
        usdt = assets.get("USDT", {})
        self._events.publish(EventRecord(action="ACCOUNT_FETCH", message="account fetch success", details={"mode": self.mode.value}))
        return {
            "balance_usdt": float(usdt.get("walletBalance", 0.0)),
            "available_usdt": float(usdt.get("availableBalance", 0.0)),
            "unrealized_pnl": float(usdt.get("unrealizedProfit", 0.0)),
            "margin_used": float(data.get("totalInitialMargin", 0.0)),
            "timestamp": int(time.time() * 1000),
        }

    async def get_positions(self) -> list[dict[str, Any]]:
        account = await self._signed_get("/fapi/v2/account")
        out: list[dict[str, Any]] = []
        for pos in account.get("positions", []):
            qty = float(pos.get("positionAmt", 0.0))
            if abs(qty) <= 0:
                continue
            out.append(pos)
        return out

    async def get_recent_fills(self, limit: int = 100, since_ts: int | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": max(1, min(limit, 1000))}
        if since_ts:
            params["startTime"] = since_ts
        fills = await self._signed_get("/fapi/v1/userTrades", params=params)
        self._events.publish(EventRecord(action="FILL", message="fills fetched", details={"count": len(fills) if isinstance(fills, list) else 0}))
        return fills if isinstance(fills, list) else []

    async def place_test_trade(self, symbol: str = "BTCUSDT", quote_value_usdt: float = 1.0, side: str = "BUY") -> dict[str, Any]:
        ticker = await self.client.get("/fapi/v1/ticker/price", params={"symbol": symbol}, signed=False)
        mark_price = float(ticker.get("price", 0.0))
        if mark_price <= 0:
            raise RuntimeError("Unable to fetch symbol price")

        quantity = quote_value_usdt / mark_price
        order_params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "MARKET",
            "quantity": f"{quantity:.6f}",
            "newClientOrderId": f"test-{int(time.time() * 1000)}",
        }
        order = await self._signed_post("/fapi/v1/order", params=order_params)
        self._events.publish(EventRecord(action="ORDER", message="test order submitted", category="ORDER", symbol=symbol, details={"quote_value_usdt": quote_value_usdt, "side": side.upper()}))
        return {
            "ok": True,
            "symbol": symbol,
            "side": side.upper(),
            "quote_value_usdt": quote_value_usdt,
            "estimated_price": mark_price,
            "quantity": float(order_params["quantity"]),
            "order": order,
        }

    async def get_income_history(self, limit: int = 100) -> list[dict[str, Any]]:
        payload = await self._signed_get("/fapi/v1/income", params={"limit": max(1, min(limit, 1000))})
        return payload if isinstance(payload, list) else []
