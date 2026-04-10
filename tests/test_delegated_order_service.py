"""Tests for delegated order operations."""

from unittest.mock import AsyncMock, Mock

import pytest

from limitless_sdk.delegated_orders import DelegatedOrderService
from limitless_sdk.types import OrderType, Side
from limitless_sdk.utils import ZERO_ADDRESS


def _order_response_payload() -> dict:
    return {
        "order": {
            "id": "order-1",
            "createdAt": "2026-03-30T12:00:00.000Z",
            "salt": "123",
            "maker": ZERO_ADDRESS,
            "signer": ZERO_ADDRESS,
            "taker": ZERO_ADDRESS,
            "tokenId": "123",
            "makerAmount": "5000000",
            "takerAmount": "9000000",
            "expiration": "0",
            "nonce": 0,
            "feeRateBps": 300,
            "side": 0,
            "signatureType": 0,
            "price": "0.55",
            "signature": "0x" + "a" * 130,
        },
        "makerMatches": [],
    }


@pytest.mark.asyncio
async def test_create_order_builds_zero_address_payload(monkeypatch):
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.post = AsyncMock(return_value=_order_response_payload())
    service = DelegatedOrderService(http_client)

    monkeypatch.setattr(
        "limitless_sdk.orders.builder.OrderBuilder._generate_salt",
        lambda self: 123,
    )

    response = await service.create_order(
        token_id="123",
        side=Side.BUY,
        order_type=OrderType.GTC,
        market_slug="bitcoin-2026",
        on_behalf_of=326,
        price=0.55,
        size=5.0,
    )

    http_client.require_auth.assert_called_once_with("create_delegated_order")
    http_client.post.assert_awaited_once()
    path, payload = http_client.post.await_args.args

    assert path == "/orders"
    assert payload["ownerId"] == 326
    assert payload["onBehalfOf"] == 326
    assert payload["order"]["maker"] == ZERO_ADDRESS
    assert payload["order"]["signer"] == ZERO_ADDRESS
    assert payload["order"]["expiration"] == "0"
    assert payload["order"]["feeRateBps"] == 300
    assert response.order.maker == ZERO_ADDRESS


@pytest.mark.asyncio
async def test_create_order_supports_fok_maker_amount(monkeypatch):
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.post = AsyncMock(
        return_value={
            **_order_response_payload(),
            "order": {
                **_order_response_payload()["order"],
                "makerAmount": "50000000",
                "takerAmount": 1,
                "price": None,
            },
        }
    )
    service = DelegatedOrderService(http_client)

    monkeypatch.setattr(
        "limitless_sdk.orders.builder.OrderBuilder._generate_salt",
        lambda self: 999,
    )

    await service.create_order(
        token_id="123",
        side=Side.BUY,
        order_type=OrderType.FOK,
        market_slug="bitcoin-2026",
        on_behalf_of=326,
        maker_amount=50.0,
    )

    _, payload = http_client.post.await_args.args
    assert payload["order"]["makerAmount"] == 50000000
    assert payload["order"]["takerAmount"] == 1
    assert "price" not in payload["order"]


@pytest.mark.asyncio
async def test_create_order_omits_post_only_for_fak(monkeypatch):
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.post = AsyncMock(return_value=_order_response_payload())
    service = DelegatedOrderService(http_client)

    monkeypatch.setattr(
        "limitless_sdk.orders.builder.OrderBuilder._generate_salt",
        lambda self: 321,
    )

    await service.create_order(
        token_id="123",
        side=Side.BUY,
        order_type=OrderType.FAK,
        market_slug="bitcoin-2026",
        on_behalf_of=326,
        price=0.55,
        size=5.0,
        post_only=True,
    )

    _, payload = http_client.post.await_args.args
    assert payload["orderType"] == "FAK"
    assert "postOnly" not in payload


@pytest.mark.asyncio
async def test_cancel_variants_pass_on_behalf_query_params():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.delete = AsyncMock(return_value={"message": "ok"})
    service = DelegatedOrderService(http_client)

    message = await service.cancel_on_behalf_of("order-1", 326)
    assert message == "ok"
    http_client.delete.assert_awaited_with(
        "/orders/order-1",
        params={"onBehalfOf": 326},
    )

    message = await service.cancel_all_on_behalf_of("bitcoin-2026", 326)
    assert message == "ok"
    http_client.delete.assert_awaited_with(
        "/orders/all/bitcoin-2026",
        params={"onBehalfOf": 326},
    )


@pytest.mark.asyncio
async def test_cancel_variants_url_encode_order_id_and_market_slug():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.delete = AsyncMock(return_value={"message": "ok"})
    service = DelegatedOrderService(http_client)

    message = await service.cancel("order/with space")
    assert message == "ok"
    http_client.delete.assert_awaited_with("/orders/order%2Fwith%20space")

    message = await service.cancel_all("market/with space")
    assert message == "ok"
    http_client.delete.assert_awaited_with("/orders/all/market%2Fwith%20space")
