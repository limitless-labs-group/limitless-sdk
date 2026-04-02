"""Tests for HttpClient.get_raw behavior."""

import pytest

from limitless_sdk.api import APIError
from limitless_sdk.api.http_client import HttpClient


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


class _MockSession:
    def __init__(self, response):
        self._response = response

    def get(self, *args, **kwargs):
        return _MockResponseContext(self._response)




@pytest.mark.asyncio
async def test_http_client_initializes_sdk_tracking_headers(monkeypatch):
    captured = {}

    class _DummySession:
        closed = False

        async def close(self):
            self.closed = True

    def _fake_client_session(*args, **kwargs):
        captured.update(kwargs)
        return _DummySession()

    monkeypatch.setattr("aiohttp.ClientSession", _fake_client_session)

    client = HttpClient(base_url="https://api.limitless.exchange", api_key="test-key")
    await client._ensure_session()

    headers = captured["headers"]
    assert "user-agent" in headers
    assert headers["user-agent"].startswith("lmts-sdk-py/")
    assert "python/" in headers["user-agent"]
    assert "x-sdk-version" in headers
    assert headers["x-sdk-version"].startswith("lmts-sdk-py/")

@pytest.mark.asyncio
async def test_get_raw_does_not_whitelist_http_errors_with_accepted_statuses():
    client = HttpClient(base_url="https://api.limitless.exchange", api_key="test-key")
    client._session = _MockSession(_MockResponse(status=404, data={"message": "not found"}))

    async def _noop_ensure():
        return None

    client._ensure_session = _noop_ensure

    with pytest.raises(APIError) as exc:
        await client.get_raw("/missing", accepted_statuses={404})

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_raw_allows_accepted_non_error_status():
    client = HttpClient(base_url="https://api.limitless.exchange", api_key="test-key")
    client._session = _MockSession(
        _MockResponse(status=301, data="", headers={"Location": "/crypto"})
    )

    async def _noop_ensure():
        return None

    client._ensure_session = _noop_ensure

    response = await client.get_raw(
        "/market-pages/by-path",
        params={"path": "/old-crypto"},
        allow_redirects=False,
        accepted_statuses={200, 301},
    )

    assert response.status == 301
    assert response.headers.get("location") == "/crypto"

