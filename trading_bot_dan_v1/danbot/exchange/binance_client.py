from __future__ import annotations

from dataclasses import dataclass

from danbot.core.config import AppConfig, Mode
from danbot.exchange.rest_client import BinanceRestClient
from danbot.exchange.ws_client import BinanceWsClient


@dataclass
class BinanceClientBundle:
    ws: BinanceWsClient
    rest: BinanceRestClient


async def discover_usdtm_symbols(
    rest: BinanceRestClient,
    min_quote_volume_24h: float,
    max_symbols_active: int,
) -> tuple[list[str], list[str]]:
    info = await rest.get("/fapi/v1/exchangeInfo")
    tickers = await rest.get("/fapi/v1/ticker/24hr")
    vol_by_symbol = {item["symbol"]: float(item.get("quoteVolume", 0.0)) for item in tickers}

    active: list[str] = []
    watch_only: list[str] = []
    for s in info.get("symbols", []):
        symbol = s.get("symbol", "")
        if s.get("contractType") != "PERPETUAL" or s.get("quoteAsset") != "USDT" or s.get("status") != "TRADING":
            continue
        if vol_by_symbol.get(symbol, 0.0) < min_quote_volume_24h:
            continue
        if len(active) < max_symbols_active:
            active.append(symbol)
        else:
            watch_only.append(symbol)
    return active, watch_only


def build_clients(config: AppConfig, api_key: str = "", api_secret: str = "") -> BinanceClientBundle:
    ws_endpoint = config.endpoints.ws_demo if config.mode == Mode.DEMO else config.endpoints.ws_real
    rest_endpoint = config.endpoints.rest_demo if config.mode == Mode.DEMO else config.endpoints.rest_real
    return BinanceClientBundle(
        ws=BinanceWsClient(endpoint=ws_endpoint),
        rest=BinanceRestClient(base_url=rest_endpoint, api_key=api_key, api_secret=api_secret),
    )
