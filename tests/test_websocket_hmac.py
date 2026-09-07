"""Tests for WebSocket HMAC authentication support."""

import pytest

from limitless_sdk.types import HMACCredentials
from limitless_sdk.websocket import WebSocketClient
from limitless_sdk.websocket.types import WebSocketConfig, WebSocketState


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.closed = False
        self.connected = True
        self.connect_calls = []
        self.handlers = {}

    def on(self, event, handler=None, namespace=None):
        if handler is not None:
            self.handlers[(namespace, event)] = handler
            return handler

        def decorator(func):
            self.handlers[(namespace, event)] = func
            return func

        return decorator

    async def connect(self, url, headers=None, transports=None, namespaces=None, wait_timeout=None):
        self.connection_headers = headers
        resolved = headers() if callable(headers) else headers
        self.connect_calls.append(
            {
                "url": url,
                "headers": resolved or {},
                "transports": transports,
                "namespaces": namespaces,
                "wait_timeout": wait_timeout,
            }
        )

    async def disconnect(self):
        self.closed = True

    async def emit(self, *args, **kwargs):
        return None


@pytest.mark.asyncio
async def test_websocket_connect_uses_hmac_headers(monkeypatch):
    fake_client = _FakeAsyncClient()
    client_kwargs = {}
    signature_calls = []

    def fake_async_client(*args, **kwargs):
        client_kwargs.update(kwargs)
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

    monkeypatch.setattr("limitless_sdk.websocket.client.AsyncClient", fake_async_client)
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
    assert fake_client.connection_headers == client._build_connection_headers


@pytest.mark.asyncio
async def test_real_socketio_reconnect_loop_reinvokes_header_callable(monkeypatch):
    import engineio
    import socketio

    counter = iter(range(1, 100))
    monkeypatch.setattr(
        "limitless_sdk.websocket.client._build_iso_timestamp",
        lambda: f"2026-03-30T12:{next(counter):02d}:00.000Z",
    )

    client = WebSocketClient(
        WebSocketConfig(
            hmac_credentials=HMACCredentials(token_id="token-123", secret="c2VjcmV0"),
        )
    )

    sio = socketio.AsyncClient(
        reconnection=True,
        reconnection_delay=0.01,
        reconnection_delay_max=0.02,
        reconnection_attempts=3,
        randomization_factor=0,
    )
    attempts = []

    async def failing_eio_connect(url, headers=None, **kwargs):
        attempts.append(dict(headers or {}))
        raise engineio.exceptions.ConnectionError("refused")

    monkeypatch.setattr(sio.eio, "connect", failing_eio_connect)

    with pytest.raises(socketio.exceptions.ConnectionError):
        await sio.connect(
            "wss://example.invalid",
            headers=client._build_connection_headers,
            transports=["websocket"],
            namespaces=["/markets"],
            retry=True,
        )

    assert len(attempts) == 4
    timestamps = [a["lmts-timestamp"] for a in attempts]
    signatures = [a["lmts-signature"] for a in attempts]
    assert len(set(timestamps)) == 4
    assert len(set(signatures)) == 4
    assert all(a["lmts-api-key"] == "token-123" for a in attempts)


@pytest.mark.asyncio
async def test_websocket_connect_uses_api_key_header_via_callable(monkeypatch):
    fake_client = _FakeAsyncClient()
    monkeypatch.setattr(
        "limitless_sdk.websocket.client.AsyncClient",
        lambda *args, **kwargs: fake_client,
    )

    client = WebSocketClient(
        WebSocketConfig(api_key="api-key-123", auto_reconnect=False)
    )

    await client.connect()

    headers = fake_client.connect_calls[0]["headers"]
    assert headers["X-API-Key"] == "api-key-123"
    assert "lmts-signature" not in headers


@pytest.mark.asyncio
async def test_websocket_connect_uses_sdk_tracking_headers_without_auth(monkeypatch):
    fake_client = _FakeAsyncClient()

    monkeypatch.setattr(
        "limitless_sdk.websocket.client.AsyncClient",
        lambda *args, **kwargs: fake_client,
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
