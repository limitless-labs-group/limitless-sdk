"""Tests for HttpClient auth modes used by api-token v3 flows."""

import base64
import hashlib
import hmac

import pytest

from limitless_sdk.api import ConflictError
from limitless_sdk.api.http_client import HttpClient
from limitless_sdk.types import HMACCredentials


class _MockResponse:
    def __init__(self, status, data, headers=None):
        self.status = status
        self._data = data
        self.headers = headers or {}

    async def json(self):
        return self._data

    async def text(self):
        return str(self._data)


class _MockResponseContext:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


class _CapturedSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, headers=None, **kwargs):
        self.calls.append(("GET", url, headers or {}, kwargs))
        return _MockResponseContext(self.response)

    def post(self, url, data=None, headers=None, **kwargs):
        self.calls.append(("POST", url, headers or {}, {"data": data, **kwargs}))
        return _MockResponseContext(self.response)

    def delete(self, url, headers=None, **kwargs):
        self.calls.append(("DELETE", url, headers or {}, kwargs))
        return _MockResponseContext(self.response)


def _expected_hmac(secret: str, timestamp: str, method: str, path: str, body: str) -> str:
    decoded_secret = base64.b64decode(secret)
    message = f"{timestamp}\n{method}\n{path}\n{body}"
    digest = hmac.new(decoded_secret, message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


@pytest.mark.asyncio
async def test_http_client_prefers_hmac_over_api_key(monkeypatch):
    timestamp = "2026-03-30T12:00:00.000Z"
    credentials = HMACCredentials(token_id="token-123", secret="c2VjcmV0")
    session = _CapturedSession(_MockResponse(200, {"ok": True}))
    client = HttpClient(
        base_url="https://api.limitless.exchange",
        api_key="plain-api-key",
        hmac_credentials=credentials,
    )
    client._session = session

    async def _noop_ensure():
        return None

    client._ensure_session = _noop_ensure
    monkeypatch.setattr("limitless_sdk.api.http_client._build_iso_timestamp", lambda: timestamp)

    await client.post("/orders", {"foo": "bar"})

    method, url, headers, kwargs = session.calls[0]
    assert method == "POST"
    assert url == "https://api.limitless.exchange/orders"
    assert headers["lmts-api-key"] == "token-123"
    assert headers["lmts-timestamp"] == timestamp
    assert headers["lmts-signature"] == _expected_hmac(
        "c2VjcmV0",
        timestamp,
        "POST",
        "/orders",
        '{"foo":"bar"}',
    )
    assert "X-API-Key" not in headers
    assert kwargs["data"] == '{"foo":"bar"}'


@pytest.mark.asyncio
async def test_http_client_identity_overrides_hmac_and_api_key():
    session = _CapturedSession(_MockResponse(200, {"ok": True}))
    client = HttpClient(
        base_url="https://api.limitless.exchange",
        api_key="plain-api-key",
        hmac_credentials=HMACCredentials(token_id="token-123", secret="c2VjcmV0"),
    )
    client._session = session

    async def _noop_ensure():
        return None

    client._ensure_session = _noop_ensure

    await client.get_with_identity("/auth/api-tokens/capabilities", "identity-token")

    _, _, headers, _ = session.calls[0]
    assert headers["identity"] == "Bearer identity-token"
    assert "X-API-Key" not in headers
    assert "lmts-api-key" not in headers
    assert "lmts-signature" not in headers


@pytest.mark.asyncio
async def test_http_client_delete_with_identity_overrides_hmac_and_api_key():
    session = _CapturedSession(_MockResponse(204, ""))
    client = HttpClient(
        base_url="https://api.limitless.exchange",
        api_key="plain-api-key",
        hmac_credentials=HMACCredentials(token_id="token-123", secret="c2VjcmV0"),
    )
    client._session = session

    async def _noop_ensure():
        return None

    client._ensure_session = _noop_ensure

    await client.delete_with_identity(
        "/portfolio/withdrawal-addresses/0x0F3262730c909408042F9Da345a916dc0e1F9787",
        "identity-token",
    )

    method, url, headers, kwargs = session.calls[0]
    assert method == "DELETE"
    assert (
        url
        == "https://api.limitless.exchange/portfolio/withdrawal-addresses/0x0F3262730c909408042F9Da345a916dc0e1F9787"
    )
    assert headers["identity"] == "Bearer identity-token"
    assert "X-API-Key" not in headers
    assert "lmts-api-key" not in headers
    assert "lmts-signature" not in headers
    assert kwargs["skip_auto_headers"] == ["Content-Type"]


@pytest.mark.asyncio
async def test_http_client_encodes_special_characters_in_query_params():
    session = _CapturedSession(_MockResponse(200, {"ok": True}))
    client = HttpClient(base_url="https://api.limitless.exchange", api_key="plain-api-key")
    client._session = session

    async def _noop_ensure():
        return None

    client._ensure_session = _noop_ensure

    await client.get(
        "/auth/api-tokens",
        params={"tokenId": "token/with space", "marketSlug": "slug/with space"},
    )

    method, url, _, _ = session.calls[0]
    assert method == "GET"
    assert (
        url
        == "https://api.limitless.exchange/auth/api-tokens?tokenId=token/with+space&marketSlug=slug/with+space"
    )


@pytest.mark.asyncio
async def test_http_client_maps_409_to_conflict_error():
    session = _CapturedSession(_MockResponse(409, {"message": "duplicate profile"}))
    client = HttpClient(base_url="https://api.limitless.exchange", api_key="plain-api-key")
    client._session = session

    async def _noop_ensure():
        return None

    client._ensure_session = _noop_ensure

    with pytest.raises(ConflictError) as exc:
        await client.post("/profiles/partner-accounts", {"displayName": "Bot"})

    assert exc.value.status_code == 409
    assert exc.value.message == "duplicate profile"


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["get", "get_raw", "post", "post_raw", "delete", "delete_raw"])
async def test_hmac_matches_request_target_sent_by_transport(method):
    from aiohttp import web

    received = []

    async def handle(request):
        body = await request.text()
        received.append(request.raw_path)
        expected = _expected_hmac(
            "c2VjcmV0",
            request.headers["lmts-timestamp"],
            request.method,
            request.raw_path,
            body,
        )
        if request.headers["lmts-signature"] != expected:
            return web.json_response({"message": "invalid signature"}, status=401)
        return web.json_response({"ok": True})

    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = runner.addresses[0][1]
        async with HttpClient(
            base_url=f"http://127.0.0.1:{port}",
            hmac_credentials=HMACCredentials(token_id="test-token", secret="c2VjcmV0"),
        ) as client:
            for path, params in [
                ("/market-pages/by-path?path=%2Fcrypto%2Fbitcoin", None),
                (
                    "/market-pages/caf%C3%A9?filter=a%2Bb&filter=space+value&filter=100%25&filter=caf%C3%A9",
                    None,
                ),
                ("/market-pages/by-path", {"path": "/crypto/bitcoin"}),
            ]:
                kwargs = {}
                if params is not None:
                    if method.startswith("post"):
                        continue
                    kwargs["params"] = params
                if method.startswith("post"):
                    kwargs["data"] = {"label": "caf\u00e9 + 100%"}
                response = await getattr(client, method)(path, **kwargs)
                assert getattr(response, "data", response) == {"ok": True}

    finally:
        await runner.cleanup()

    expected_paths = [
        "/market-pages/by-path?path=/crypto/bitcoin",
        "/market-pages/caf%C3%A9?filter=a%2Bb&filter=space+value&filter=100%25&filter=caf%C3%A9",
    ]
    if not method.startswith("post"):
        expected_paths.append("/market-pages/by-path?path=/crypto/bitcoin")
    assert received == expected_paths
