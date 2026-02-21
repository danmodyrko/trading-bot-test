import asyncio

from aiohttp import ClientResponseError

from danbot.exchange.rest_client import BinanceRestClient


class _FakeResponse:
    def __init__(self, status: int, text_payload: str, json_payload):
        self.status = status
        self._text_payload = text_payload
        self._json_payload = json_payload
        self.request_info = None
        self.history = []
        self.headers = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return self._text_payload

    async def json(self, content_type=None):
        if isinstance(self._json_payload, Exception):
            raise self._json_payload
        return self._json_payload


class _FakeSession:
    def __init__(self, response: _FakeResponse):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, path, params=None, timeout=None):
        return self._response


def test_get_raises_client_response_error_with_binance_details(monkeypatch):
    response = _FakeResponse(status=400, text_payload='{"code":-2015,"msg":"Invalid API-key"}', json_payload={"code": -2015, "msg": "Invalid API-key"})
    monkeypatch.setattr("danbot.exchange.rest_client.aiohttp.ClientSession", lambda *args, **kwargs: _FakeSession(response))
    client = BinanceRestClient(base_url="https://example.test", api_key="k", api_secret="s")

    async def _run():
        await client.get("/fapi/v2/account", signed=True)

    try:
        asyncio.run(_run())
        assert False, "Expected ClientResponseError"
    except ClientResponseError as exc:
        assert exc.status == 400
        assert "code=-2015" in exc.message
        assert "Invalid API-key" in exc.message
