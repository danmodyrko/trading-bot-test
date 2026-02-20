from __future__ import annotations

from dataclasses import dataclass

from danbot.core.config import AppConfig, Mode
from danbot.exchange.rest_client import BinanceRestClient
from danbot.exchange.ws_client import BinanceWsClient


@dataclass
class BinanceClientBundle:
    ws: BinanceWsClient
    rest: BinanceRestClient


def build_clients(config: AppConfig, api_key: str = "", api_secret: str = "") -> BinanceClientBundle:
    ws_endpoint = config.endpoints.ws_demo if config.mode == Mode.DEMO else config.endpoints.ws_real
    rest_endpoint = config.endpoints.rest_demo if config.mode == Mode.DEMO else config.endpoints.rest_real
    return BinanceClientBundle(
        ws=BinanceWsClient(endpoint=ws_endpoint),
        rest=BinanceRestClient(base_url=rest_endpoint, api_key=api_key, api_secret=api_secret),
    )
