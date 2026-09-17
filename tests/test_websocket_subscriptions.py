"""Market subscriptions retain their full identity across reconnects."""

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
    socket.call = AsyncMock(return_value={})
    client._sio = socket
    client._setup_internal_handlers()
    client._state = WebSocketState.CONNECTED
    return client, socket


async def reconnect(socket):
    socket.emit.reset_mock()
    await socket._trigger_event('disconnect', DEFAULT_NAMESPACE, 'transport error')
    await socket._trigger_event('connect', DEFAULT_NAMESPACE)


@pytest.mark.asyncio
@pytest.mark.parametrize('options_a,options_b', [
    ({'marketSlugs': ['solana']}, {'marketSlugs': ['xrp']}),
    ({'marketAddresses': ['0x01']}, {'marketAddresses': ['0x02']}),
    ({'marketSlug': 'solana'}, {'marketSlug': 'xrp'}),
    ({'marketAddress': '0x01'}, {'marketAddress': '0x02'}),
    ({'filters': {'league': 'a'}}, {'filters': {'league': 'b'}}),
])
async def test_separate_subscriptions_replay_and_unsubscribe_independently(options_a, options_b):
    client, socket = connected_client()
    channel = 'subscribe_market_prices'
    await client.subscribe(channel, options_a)
    await client.subscribe(channel, options_b)

    await reconnect(socket)
    assert socket.emit.await_args_list == [
        call(channel, options_a, namespace=DEFAULT_NAMESPACE),
        call(channel, options_b, namespace=DEFAULT_NAMESPACE),
    ]

    await client.unsubscribe(channel, options_a)
    socket.call.assert_awaited_once_with(
        'unsubscribe', {'channel': channel, **options_a},
        namespace=DEFAULT_NAMESPACE, timeout=5.0,
    )
    await reconnect(socket)
    socket.emit.assert_awaited_once_with(channel, options_b, namespace=DEFAULT_NAMESPACE)


@pytest.mark.asyncio
async def test_equivalent_options_deduplicate_and_unsubscribe_regardless_of_order():
    client, socket = connected_client()
    channel = 'subscribe_market_prices'
    await client.subscribe(channel, {
        'marketSlugs': ['solana', 'xrp', 'solana'],
        'filters': {'first': 1, 'second': 2},
    })
    equivalent = {
        'filters': {'second': 2, 'first': 1},
        'marketSlugs': ['xrp', 'solana'],
    }
    await client.subscribe(channel, equivalent)
    await reconnect(socket)
    socket.emit.assert_awaited_once_with(channel, equivalent, namespace=DEFAULT_NAMESPACE)

    await client.unsubscribe(channel, {
        'marketSlugs': ['solana', 'xrp'],
        'filters': {'first': 1, 'second': 2},
    })
    await reconnect(socket)
    socket.emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_reusing_options_does_not_change_saved_subscriptions():
    client, socket = connected_client()
    options = {'marketSlugs': ['solana'], 'filters': {'tags': ['original']}}
    await client.subscribe('subscribe_market_prices', options)
    options['marketSlugs'][0] = 'xrp'
    options['filters']['tags'].append('new')
    await client.subscribe('subscribe_market_prices', options)

    await reconnect(socket)
    assert socket.emit.await_args_list == [
        call('subscribe_market_prices', {
            'marketSlugs': ['solana'], 'filters': {'tags': ['original']},
        }, namespace=DEFAULT_NAMESPACE),
        call('subscribe_market_prices', options, namespace=DEFAULT_NAMESPACE),
    ]


@pytest.mark.asyncio
async def test_global_subscriptions_remain_distinct_by_channel():
    client, socket = connected_client()
    await client.subscribe('subscribe_order_events')
    await client.subscribe('subscribe_transactions')
    await reconnect(socket)
    assert socket.emit.await_args_list == [
        call('subscribe_order_events', {}, namespace=DEFAULT_NAMESPACE),
        call('subscribe_transactions', {}, namespace=DEFAULT_NAMESPACE),
    ]
