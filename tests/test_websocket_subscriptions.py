"""Reconnects restore the latest subscription per channel, as the gateway does."""

import asyncio
from unittest.mock import AsyncMock, call

import pytest
from socketio import AsyncClient

from limitless_sdk.websocket import WebSocketClient, WebSocketConfig
from limitless_sdk.websocket.client import DEFAULT_NAMESPACE
from limitless_sdk.websocket.types import WebSocketState


def connected_client():
    client = WebSocketClient(WebSocketConfig(api_key='test-key'))
    socket = AsyncClient()
    socket.emit = AsyncMock()
    client._sio = socket
    client._setup_internal_handlers()
    client._state = WebSocketState.CONNECTED
    return client, socket


async def reconnect(socket):
    socket.emit.reset_mock()
    await socket._trigger_event('disconnect', DEFAULT_NAMESPACE, 'transport error')
    await socket._trigger_event('connect', DEFAULT_NAMESPACE)


@pytest.mark.asyncio
@pytest.mark.parametrize('channel', ['subscribe_market_prices', 'subscribe_positions'])
@pytest.mark.parametrize('options_a,options_b', [
    ({'marketSlugs': ['solana']}, {'marketSlugs': ['xrp']}),
    ({'marketAddresses': ['0x01']}, {'marketAddresses': ['0x02']}),
    ({'marketSlug': 'solana'}, {'marketSlug': 'xrp'}),
    ({'marketAddress': '0x01'}, {'marketAddress': '0x02'}),
])
async def test_latest_selection_is_replayed_even_when_revisiting_a_market(channel, options_a, options_b):
    client, socket = connected_client()
    await client.subscribe(channel, options_a)
    await client.subscribe(channel, options_b)
    await reconnect(socket)
    socket.emit.assert_awaited_once_with(channel, options_b, namespace=DEFAULT_NAMESPACE)

    # A -> B -> A must not replay A then B and switch the server back to B.
    await client.subscribe(channel, options_a)
    await reconnect(socket)
    socket.emit.assert_awaited_once_with(channel, options_a, namespace=DEFAULT_NAMESPACE)


@pytest.mark.asyncio
@pytest.mark.parametrize('channel', ['subscribe_market_prices', 'subscribe_positions'])
async def test_market_rotation_keeps_one_saved_payload(channel):
    client, socket = connected_client()
    for index in range(100):
        await client.subscribe(channel, {'marketSlugs': [f'market-{index}']})
    assert len(client._subscriptions) == 1
    await reconnect(socket)
    socket.emit.assert_awaited_once_with(
        channel, {'marketSlugs': ['market-99']}, namespace=DEFAULT_NAMESPACE,
    )


@pytest.mark.asyncio
async def test_combined_market_selection_replays_in_one_payload():
    client, socket = connected_client()
    channel = 'subscribe_market_prices'
    await client.subscribe(channel, {'marketSlugs': ['old-market']})
    combined = {'marketSlugs': ['solana', 'xrp']}
    await client.subscribe(channel, combined)
    await reconnect(socket)
    socket.emit.assert_awaited_once_with(channel, combined, namespace=DEFAULT_NAMESPACE)


@pytest.mark.asyncio
async def test_caller_mutation_does_not_change_the_latest_saved_payload():
    client, socket = connected_client()
    channel = 'subscribe_market_prices'
    options = {'marketSlugs': ['solana'], 'filters': {'tags': ['original']}}
    await client.subscribe(channel, options)
    options['marketSlugs'][0] = 'xrp'
    options['filters']['tags'].append('new')
    await reconnect(socket)
    socket.emit.assert_awaited_once_with(channel, {
        'marketSlugs': ['solana'], 'filters': {'tags': ['original']},
    }, namespace=DEFAULT_NAMESPACE)

    await client.subscribe(channel, options)
    options['marketSlugs'].clear()
    options['filters']['tags'].clear()
    await reconnect(socket)
    socket.emit.assert_awaited_once_with(channel, {
        'marketSlugs': ['xrp'], 'filters': {'tags': ['original', 'new']},
    }, namespace=DEFAULT_NAMESPACE)


@pytest.mark.asyncio
async def test_channels_keep_independent_latest_payloads():
    client, socket = connected_client()
    await client.subscribe('subscribe_market_prices', {'marketSlugs': ['old-market']})
    await client.subscribe('subscribe_positions', {'marketSlugs': ['xrp']})
    await client.subscribe('subscribe_order_events')
    await client.subscribe('subscribe_market_prices', {'marketSlugs': ['solana']})
    await reconnect(socket)
    assert socket.emit.await_args_list == [
        call('subscribe_market_prices', {'marketSlugs': ['solana']}, namespace=DEFAULT_NAMESPACE),
        call('subscribe_positions', {'marketSlugs': ['xrp']}, namespace=DEFAULT_NAMESPACE),
        call('subscribe_order_events', {}, namespace=DEFAULT_NAMESPACE),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize('channel,previous,replacement', [
    ('subscribe_market_prices', {'marketSlugs': ['solana']}, {'marketSlugs': ['xrp']}),
    ('subscribe_order_events', {}, {'filters': {'marketSlug': 'xrp'}}),
])
async def test_failed_replacement_restores_previous_subscription(channel, previous, replacement):
    client, socket = connected_client()
    await client.subscribe(channel, previous)
    socket.emit.side_effect = ConnectionError('transport dropped')

    with pytest.raises(ConnectionError, match='transport dropped'):
        await client.subscribe(channel, replacement)

    socket.emit.side_effect = None
    await reconnect(socket)
    socket.emit.assert_awaited_once_with(channel, previous, namespace=DEFAULT_NAMESPACE)


@pytest.mark.asyncio
async def test_failed_first_subscription_is_not_replayed():
    client, socket = connected_client()
    socket.emit.side_effect = ConnectionError('transport dropped')
    with pytest.raises(ConnectionError, match='transport dropped'):
        await client.subscribe('subscribe_market_prices', {'marketSlugs': ['solana']})

    socket.emit.side_effect = None
    await reconnect(socket)
    socket.emit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('newer_market', ['xrp', 'bitcoin'])
async def test_failed_earlier_attempt_does_not_erase_newer_subscription(newer_market):
    client, socket = connected_client()
    channel = 'subscribe_market_prices'
    await client.subscribe(channel, {'marketSlugs': ['solana']})
    started = asyncio.Event()
    release = asyncio.Event()

    async def emit_with_delayed_failure(*args, **kwargs):
        if not started.is_set():
            started.set()
            await release.wait()
            raise ConnectionError('earlier attempt failed')

    socket.emit.side_effect = emit_with_delayed_failure
    pending = asyncio.create_task(client.subscribe(channel, {'marketSlugs': ['xrp']}))
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        # Include identical payloads: ownership must be checked by identity.
        await client.subscribe(channel, {'marketSlugs': [newer_market]})
    finally:
        release.set()
        results = await asyncio.gather(pending, return_exceptions=True)
    assert isinstance(results[0], ConnectionError)

    socket.emit.side_effect = None
    await reconnect(socket)
    socket.emit.assert_awaited_once_with(
        channel, {'marketSlugs': [newer_market]}, namespace=DEFAULT_NAMESPACE,
    )
