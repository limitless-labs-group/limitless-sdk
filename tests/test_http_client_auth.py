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
        hmac_credentials=HMACCredentials(tokenId="token-123", secret="c2VjcmV0"),
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
