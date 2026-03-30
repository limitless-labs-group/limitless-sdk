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
        return None


@pytest.mark.asyncio
async def test_websocket_connect_uses_hmac_headers(monkeypatch):
    fake_client = _FakeAsyncClient()

    monkeypatch.setattr(
        "limitless_sdk.websocket.client.AsyncClient",
        lambda *args, **kwargs: fake_client,
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
    headers = fake_client.connect_calls[0]["headers"]
    assert headers["lmts-api-key"] == "token-123"
    assert "lmts-signature" in headers
    assert "X-API-Key" not in headers


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
