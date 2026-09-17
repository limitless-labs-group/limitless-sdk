"""Tests for WebSocket HMAC authentication support."""

import pytest

from limitless_sdk.types import HMACCredentials
from limitless_sdk.websocket import WebSocketClient
from limitless_sdk.websocket.client import DEFAULT_NAMESPACE, _FreshHeadersAsyncClient
from limitless_sdk.websocket.types import WebSocketConfig, WebSocketState


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.closed = False
        self.connected = True
        self.connect_calls = []
        self.emit_calls = []
        self.handlers = {}
        self.headers_factory = None

    def on(self, event, handler=None, namespace=None):
        if handler is not None:
            self.handlers[(namespace, event)] = handler
            return handler

        def decorator(func):
            self.handlers[(namespace, event)] = func
            return func

        return decorator

    async def connect(self, url, headers=None, transports=None, namespaces=None, wait_timeout=None):
        if self.headers_factory is not None:
            headers = self.headers_factory()
        self.connect_calls.append(
            {
                "url": url,
                "headers": headers or {},
                "transports": transports,
                "namespaces": namespaces,
                "wait_timeout": wait_timeout,
            }
        )

    async def disconnect(self):
        self.closed = True

    async def emit(self, *args, **kwargs):
        self.emit_calls.append({"args": args, "kwargs": kwargs})
        return None


@pytest.mark.asyncio
async def test_websocket_connect_uses_hmac_headers(monkeypatch):
    fake_client = _FakeAsyncClient()
    client_kwargs = {}
    signature_calls = []

    def fake_async_client(headers_factory, *args, **kwargs):
        client_kwargs.update(kwargs)
        fake_client.headers_factory = headers_factory
        return fake_client

    def fake_compute_hmac_signature(secret, timestamp, method, path, body):
        signature_calls.append(
            {
                "secret": secret,
                "timestamp": timestamp,
                "method": method,
                "path": path,
                "body": body,
            }
        )
        return "signature-123"

    monkeypatch.setattr("limitless_sdk.websocket.client._FreshHeadersAsyncClient", fake_async_client)
    monkeypatch.setattr(
        "limitless_sdk.websocket.client.compute_hmac_signature",
        fake_compute_hmac_signature,
    )
    monkeypatch.setattr(
        "limitless_sdk.websocket.client._build_iso_timestamp",
        lambda: "2026-03-30T12:00:00.000Z",
    )

    client = WebSocketClient(
        WebSocketConfig(
            hmac_credentials=HMACCredentials(
                token_id="token-123",
                secret="c2VjcmV0",
            ),
            auto_reconnect=False,
        )
    )

    await client.connect()

    assert client.state == WebSocketState.CONNECTED
    assert client_kwargs["timestamp_requests"] is False
    assert signature_calls == [
        {
            "secret": "c2VjcmV0",
            "timestamp": "2026-03-30T12:00:00.000Z",
            "method": "GET",
            "path": "/socket.io/?transport=websocket&EIO=4",
            "body": "",
        }
    ]
    headers = fake_client.connect_calls[0]["headers"]
    assert headers["x-sdk-version"].startswith("lmts-sdk-py/")
    assert headers["user-agent"].startswith("lmts-sdk-py/")
    assert "python/" in headers["user-agent"]
    assert headers["lmts-api-key"] == "token-123"
    assert headers["lmts-signature"] == "signature-123"
    assert "X-API-Key" not in headers


@pytest.mark.asyncio
async def test_websocket_connect_uses_sdk_tracking_headers_without_auth(monkeypatch):
    fake_client = _FakeAsyncClient()

    def fake_async_client(headers_factory, *args, **kwargs):
        fake_client.headers_factory = headers_factory
        return fake_client

    monkeypatch.setattr(
        "limitless_sdk.websocket.client._FreshHeadersAsyncClient",
        fake_async_client,
    )

    client = WebSocketClient(
        WebSocketConfig(
            auto_reconnect=False,
        )
    )

    await client.connect()

    assert client.state == WebSocketState.CONNECTED
    headers = fake_client.connect_calls[0]["headers"]
    assert headers["x-sdk-version"].startswith("lmts-sdk-py/")
    assert headers["user-agent"].startswith("lmts-sdk-py/")
    assert "python/" in headers["user-agent"]


@pytest.mark.asyncio
async def test_websocket_authenticated_subscription_allows_hmac_without_api_key():
    client = WebSocketClient(
        WebSocketConfig(
            hmac_credentials=HMACCredentials(
                token_id="token-123",
                secret="c2VjcmV0",
            ),
            auto_reconnect=False,
        )
    )
    client._sio = _FakeAsyncClient()
    client._state = WebSocketState.CONNECTED

    await client.subscribe("subscribe_positions", {"marketSlugs": ["market-1"]})
    await client.subscribe("subscribe_order_events")


@pytest.mark.asyncio
async def test_websocket_subscription_rejects_unsupported_channel():
    client = WebSocketClient(WebSocketConfig(auto_reconnect=False))
    client._sio = _FakeAsyncClient()
    client._state = WebSocketState.CONNECTED

    with pytest.raises(ValueError, match="Unsupported websocket subscription channel 'trades'"):
        await client.subscribe("trades")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_hmac_headers_are_regenerated_for_every_connection_attempt(monkeypatch):
    timestamps = iter([
        "2026-09-14T09:15:00.000Z",
        "2026-09-14T09:16:00.000Z",
    ])
    connection_headers = []

    async def fake_connect(self, url, **kwargs):
        connection_headers.append(kwargs["headers"])

    monkeypatch.setattr(
        "limitless_sdk.websocket.client._build_iso_timestamp",
        lambda: next(timestamps),
    )
    monkeypatch.setattr(
        "limitless_sdk.websocket.client.compute_hmac_signature",
        lambda secret, timestamp, method, path, body: f"signature:{timestamp}",
    )
    monkeypatch.setattr(
        "limitless_sdk.websocket.client.AsyncClient.connect",
        fake_connect,
    )

    client = WebSocketClient(
        WebSocketConfig(
            hmac_credentials=HMACCredentials(
                token_id="token-123",
                secret="c2VjcmV0",
            ),
        )
    )
    socket = _FreshHeadersAsyncClient(client._build_connection_headers)

    await socket.connect("wss://ws.limitless.exchange")
    await socket.connect(
        "wss://ws.limitless.exchange",
        headers={"lmts-timestamp": "stale"},
    )

    assert [headers["lmts-timestamp"] for headers in connection_headers] == [
        "2026-09-14T09:15:00.000Z",
        "2026-09-14T09:16:00.000Z",
    ]
    assert [headers["lmts-signature"] for headers in connection_headers] == [
        "signature:2026-09-14T09:15:00.000Z",
        "signature:2026-09-14T09:16:00.000Z",
    ]


@pytest.mark.asyncio
async def test_markets_reconnect_restores_subscriptions():
    client = WebSocketClient(WebSocketConfig(api_key="api-key"))
    fake_client = _FakeAsyncClient()
    client._sio = fake_client
    client._subscriptions = {
        "subscribe_order_events": {},
    }
    client._state = WebSocketState.CONNECTED

    client._setup_internal_handlers()

    assert (DEFAULT_NAMESPACE, "connect") in fake_client.handlers
    assert (DEFAULT_NAMESPACE, "disconnect") in fake_client.handlers
    assert (DEFAULT_NAMESPACE, "connect_error") in fake_client.handlers
    assert (None, "reconnect") not in fake_client.handlers

    await fake_client.handlers[(DEFAULT_NAMESPACE, "disconnect")]()
    assert client.state == WebSocketState.DISCONNECTED

    await fake_client.handlers[(DEFAULT_NAMESPACE, "connect")]()

    assert client.state == WebSocketState.CONNECTED
    assert fake_client.emit_calls == [
        {
            "args": ("subscribe_order_events", {}),
            "kwargs": {"namespace": DEFAULT_NAMESPACE},
        }
    ]
