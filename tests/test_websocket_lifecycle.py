"""User callbacks must not disable Socket.IO lifecycle recovery."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from socketio import AsyncClient

from limitless_sdk.websocket import WebSocketClient, WebSocketConfig
from limitless_sdk.websocket.client import DEFAULT_NAMESPACE
from limitless_sdk.websocket.types import WebSocketState


def attach_socket(client):
    socket = AsyncClient()
    socket._connect_event = asyncio.Event()
    socket.emit = AsyncMock()
    client._sio = socket
    client._setup_internal_handlers()
    client._attach_pending_listeners()
    return socket


async def reconnect(socket):
    await socket._trigger_event('disconnect', DEFAULT_NAMESPACE, 'transport error')
    socket.namespaces.clear()
    await socket._handle_connect(DEFAULT_NAMESPACE, {'sid': 'reconnected'})


@pytest.mark.asyncio
@pytest.mark.parametrize('event', ['connect', 'disconnect'])
@pytest.mark.parametrize('registration', ['before', 'after'])
@pytest.mark.parametrize('asynchronous', [False, True])
async def test_user_callback_preserves_subscription_recovery(event, registration, asynchronous):
    client = WebSocketClient(WebSocketConfig(api_key='test-key'))
    observed_states = []

    def observe(*args):
        observed_states.append(client.state)

    callback = AsyncMock(side_effect=observe) if asynchronous else Mock(side_effect=observe)
    if registration == 'before':
        client.on(event, callback)
    socket = attach_socket(client)
    client._state = WebSocketState.CONNECTING
    await socket._handle_connect(DEFAULT_NAMESPACE, {'sid': 'initial'})
    if registration == 'after':
        client.on(event, callback)
    callback.reset_mock()
    observed_states.clear()
    await client.subscribe('subscribe_order_events')
    socket.emit.reset_mock()

    await reconnect(socket)

    assert client.is_connected()
    socket.emit.assert_awaited_once_with('subscribe_order_events', {}, namespace=DEFAULT_NAMESPACE)
    callback.assert_called_once_with(*(() if event == 'connect' else ('transport error',)))
    expected_state = WebSocketState.CONNECTED if event == 'connect' else WebSocketState.DISCONNECTED
    assert observed_states == [expected_state]
    if asynchronous:
        assert callback.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('event', ['connect', 'disconnect', 'connect_error'])
async def test_failing_callback_does_not_interrupt_lifecycle(event):
    client = WebSocketClient(WebSocketConfig())
    socket = attach_socket(client)
    client._state = WebSocketState.CONNECTED
    await client.subscribe('subscribe_market_prices', {'marketSlugs': ['solana']})
    socket.emit.reset_mock()
    callback = Mock(side_effect=TypeError('user callback failure'))
    client.on(event, callback)

    if event == 'connect_error':
        await socket._trigger_event(event, DEFAULT_NAMESPACE, {'message': 'rejected'})
        assert client.state == WebSocketState.ERROR
    await reconnect(socket)

    assert client.is_connected()
    assert socket.emit.await_count == 1
    callback.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('removal', ['once', 'off', 'off_specific'])
async def test_removing_user_callback_preserves_internal_handler(removal):
    client = WebSocketClient(WebSocketConfig())
    socket = attach_socket(client)
    client._state = WebSocketState.CONNECTED
    await client.subscribe('subscribe_market_prices', {'marketSlugs': ['solana']})
    socket.emit.reset_mock()
    callback = Mock()
    if removal == 'once':
        client.once('connect', callback)
    else:
        client.on('connect', callback)
        if removal == 'off_specific':
            client.off('connect', callback)
        else:
            client.off('connect')

    await reconnect(socket)
    await reconnect(socket)

    assert client.is_connected()
    assert socket.emit.await_count == 2
    assert callback.call_count == (1 if removal == 'once' else 0)


@pytest.mark.asyncio
async def test_legacy_disconnect_callback_and_removal_before_connect():
    client = WebSocketClient(WebSocketConfig())
    removed = Mock()
    client.on('connect', removed)
    client.off('connect', removed)
    callback = Mock()

    @client.on('disconnect')
    async def on_disconnect():
        callback()

    socket = attach_socket(client)
    await reconnect(socket)

    callback.assert_called_once_with()
    removed.assert_not_called()
    assert client.is_connected()
