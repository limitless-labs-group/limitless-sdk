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
        self.calls = []

    def get(self, *args, **kwargs):
        self.calls.append(("get", args, kwargs))
        return _MockResponseContext(self._response)

    def post(self, *args, **kwargs):
        self.calls.append(("post", args, kwargs))
        return _MockResponseContext(self._response)

    def delete(self, *args, **kwargs):
        self.calls.append(("delete", args, kwargs))
        return _MockResponseContext(self._response)


def _install_session(client, response):
    session = _MockSession(response)
    client._session = session

    async def _noop_ensure():
        return None

    client._ensure_session = _noop_ensure
    return session




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


@pytest.mark.asyncio
async def test_post_raw_returns_raw_response_with_lowercased_headers():
    client = HttpClient(base_url="https://api.limitless.exchange", api_key="test-key")
    session = _install_session(
        client,
        _MockResponse(
            status=201,
            data={"status": "SUBMITTED"},
            headers={"Content-Type": "application/json", "X-Trace": "abc"},
        ),
    )

    response = await client.post_raw("/amm/buy", {"market": "m"})

    assert response.status == 201
    assert response.data == {"status": "SUBMITTED"}
    assert response.headers.get("content-type") == "application/json"
    assert response.headers.get("x-trace") == "abc"
    assert session.calls[0][0] == "post"


@pytest.mark.asyncio
async def test_post_raw_raises_typed_error_on_http_error():
    client = HttpClient(base_url="https://api.limitless.exchange", api_key="test-key")
    _install_session(client, _MockResponse(status=422, data={"message": "too small"}))

    from limitless_sdk.api.errors import UnprocessableEntityError

    with pytest.raises(UnprocessableEntityError) as exc:
        await client.post_raw("/amm/buy", {"market": "m"})

    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_post_raw_whitelists_accepted_error_status():
    client = HttpClient(base_url="https://api.limitless.exchange", api_key="test-key")
    _install_session(client, _MockResponse(status=409, data={"message": "conflict"}))

    response = await client.post_raw(
        "/orders/cancel-replace", {"cancel": {}}, accepted_statuses={409}
    )

    assert response.status == 409
    assert response.data == {"message": "conflict"}


@pytest.mark.asyncio
async def test_delete_raw_returns_raw_response():
    client = HttpClient(base_url="https://api.limitless.exchange", api_key="test-key")
    session = _install_session(
        client,
        _MockResponse(status=200, data={"message": "ok"}, headers={"X-Trace": "z"}),
    )

    response = await client.delete_raw("/orders/order-1")

    assert response.status == 200
    assert response.data == {"message": "ok"}
    assert response.headers.get("x-trace") == "z"
    assert session.calls[0][0] == "delete"


@pytest.mark.asyncio
async def test_delete_raw_raises_typed_error_on_http_error():
    client = HttpClient(base_url="https://api.limitless.exchange", api_key="test-key")
    _install_session(client, _MockResponse(status=404, data={"message": "not found"}))

    with pytest.raises(APIError) as exc:
        await client.delete_raw("/orders/missing")

    assert exc.value.status_code == 404

