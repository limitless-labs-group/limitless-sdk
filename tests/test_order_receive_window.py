"""Tests for optional receive-window order creation controls."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from limitless_sdk.client import LimitlessClient
from limitless_sdk.models import CreateOrderDto as LegacyCreateOrderDto
from limitless_sdk.models import Order as LegacyOrder
from limitless_sdk.orders.client import OrderClient
from limitless_sdk.types import OrderType, Side, UserData
from limitless_sdk.types.orders import UnsignedOrder
from limitless_sdk.utils import ZERO_ADDRESS


WALLET_ADDRESS = "0x0000000000000000000000000000000000000001"
VENUE_EXCHANGE = "0x0000000000000000000000000000000000000002"
SIGNATURE = "0x" + "a" * 130


def _order_response_payload() -> dict:
    return {
        "order": {
            "id": "order-1",
            "createdAt": "2026-03-30T12:00:00.000Z",
            "salt": "123",
            "maker": WALLET_ADDRESS,
            "signer": WALLET_ADDRESS,
            "taker": ZERO_ADDRESS,
            "tokenId": "123",
            "makerAmount": "5500000",
            "takerAmount": "10000000",
            "expiration": "0",
            "nonce": 0,
            "feeRateBps": 300,
            "side": 0,
            "signatureType": 0,
            "price": "0.55",
            "signature": SIGNATURE,
        },
        "makerMatches": [],
    }


def _unsigned_order() -> UnsignedOrder:
    return UnsignedOrder(
        salt=123,
        maker=WALLET_ADDRESS,
        signer=WALLET_ADDRESS,
        taker=ZERO_ADDRESS,
        token_id="123",
        maker_amount=5_500_000,
        taker_amount=10_000_000,
        expiration=0,
        nonce=0,
        fee_rate_bps=300,
        side=Side.BUY,
        signature_type=0,
        price=0.55,
    )


def _order_client_harness():
    http_client = Mock()
    http_client.post = AsyncMock(return_value=_order_response_payload())

    client = OrderClient(
        http_client=http_client,
        wallet=SimpleNamespace(address=WALLET_ADDRESS),
    )
    client._cached_user_data = UserData(user_id=42, fee_rate_bps=300)
    client._builder = Mock()
    client._builder.build_order = Mock(return_value=_unsigned_order())
    client._signer = Mock()
    client._signer.sign_order = AsyncMock(return_value=SIGNATURE)
    client._market_fetcher = Mock()
    client._market_fetcher.get_venue = Mock(
        return_value=SimpleNamespace(exchange=VENUE_EXCHANGE, adapter=None)
    )

    return client, http_client


@pytest.mark.asyncio
async def test_order_client_omits_receive_window_by_default():
    client, http_client = _order_client_harness()

    await client.create_order(
        token_id="123",
        side=Side.BUY,
        order_type=OrderType.GTC,
        market_slug="bitcoin-2026",
        price=0.55,
        size=10,
    )

    _, payload = http_client.post.await_args.args
    assert "timestamp" not in payload
    assert "recvWindow" not in payload
    assert "timestamp" not in payload["order"]
    assert "recvWindow" not in payload["order"]


@pytest.mark.asyncio
async def test_order_client_sends_receive_window_top_level_only():
    client, http_client = _order_client_harness()

    await client.create_order(
        token_id="123",
        side=Side.BUY,
        order_type=OrderType.GTC,
        market_slug="bitcoin-2026",
        price=0.55,
        size=10,
        timestamp=1_770_000_000_000,
        recv_window=1500,
    )

    _, payload = http_client.post.await_args.args
    signed_order = client._signer.sign_order.await_args.args[0]
    signed_payload = signed_order.model_dump(by_alias=True)

    assert payload["timestamp"] == 1_770_000_000_000
    assert payload["recvWindow"] == 1500
    assert "timestamp" not in payload["order"]
    assert "recvWindow" not in payload["order"]
    assert "timestamp" not in signed_payload
    assert "recvWindow" not in signed_payload


@pytest.mark.asyncio
async def test_order_client_auto_stamps_timestamp_when_recv_window_is_supplied(monkeypatch):
    monkeypatch.setattr(
        "limitless_sdk.orders.receive_window.time.time",
        lambda: 1_770_000_000.0,
    )
    client, http_client = _order_client_harness()

    await client.create_order(
        token_id="123",
        side=Side.BUY,
        order_type=OrderType.GTC,
        market_slug="bitcoin-2026",
        price=0.55,
        size=10,
        recv_window=1500,
    )

    _, payload = http_client.post.await_args.args
    assert payload["timestamp"] == 1_770_000_000_000
    assert payload["recvWindow"] == 1500


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"timestamp": -1}, "timestamp must be a non-negative integer"),
        ({"timestamp": 1.5}, "timestamp must be a non-negative integer"),
        ({"recv_window": 0}, "recv_window must be between 1 and 10000 milliseconds"),
        ({"recv_window": 10001}, "recv_window must be between 1 and 10000 milliseconds"),
        ({"recv_window": 1500.5}, "recv_window must be an integer"),
    ],
)
async def test_order_client_rejects_invalid_receive_window_before_post(kwargs, message):
    client, http_client = _order_client_harness()

    with pytest.raises(ValueError, match=message):
        await client.create_order(
            token_id="123",
            side=Side.BUY,
            order_type=OrderType.GTC,
            market_slug="bitcoin-2026",
            price=0.55,
            size=10,
            **kwargs,
        )

    http_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_legacy_create_order_auto_stamps_receive_window(monkeypatch):
    monkeypatch.setattr(
        "limitless_sdk.orders.receive_window.time.time",
        lambda: 1_770_000_000.0,
    )
    client = LimitlessClient(private_key="0x" + "a" * 64)
    client.get_user_profile = AsyncMock(return_value={"id": 42})
    client._get_token_id_for_market = AsyncMock(return_value="123")
    client.get_market = AsyncMock(return_value={"marketType": "single"})
    client._calculate_amounts = AsyncMock(return_value=(5_500_000, 10_000_000))
    client._generate_salt = Mock(return_value=123)
    client._sign_order = Mock(return_value=SIGNATURE)

    dto = await client.create_order(
        market_id="unused",
        market_slug="bitcoin-2026",
        outcome_index=0,
        side=0,
        amount=10,
        price=0.55,
        recv_window=1500,
    )

    assert dto.timestamp == 1_770_000_000_000
    assert dto.recvWindow == 1500
    assert not hasattr(dto.order, "timestamp")
    assert not hasattr(dto.order, "recvWindow")


class _FakePostResponse:
    status = 201

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def json(self):
        return {"ok": True}

    async def text(self):
        return ""


class _FakeSession:
    def __init__(self):
        self.payload = None

    def post(self, _url, *, json):
        self.payload = json
        return _FakePostResponse()


def _legacy_order_dto(**kwargs) -> LegacyCreateOrderDto:
    return LegacyCreateOrderDto(
        order=LegacyOrder(
            salt=123,
            maker=WALLET_ADDRESS,
            signer=WALLET_ADDRESS,
            tokenId="123",
            makerAmount=5_500_000,
            takerAmount=10_000_000,
            feeRateBps=300,
            side=0,
            signature=SIGNATURE,
            signatureType=0,
            taker=ZERO_ADDRESS,
            expiration="0",
            nonce=0,
            price=0.55,
        ),
        ownerId=42,
        orderType="GTC",
        marketSlug="bitcoin-2026",
        **kwargs,
    )


@pytest.mark.asyncio
async def test_legacy_place_order_omits_empty_receive_window_fields():
    client = LimitlessClient(private_key="0x" + "a" * 64)
    client.ensure_authenticated = AsyncMock()
    client.ensure_session = AsyncMock()
    client.session = _FakeSession()

    await client.place_order(_legacy_order_dto())

    assert "timestamp" not in client.session.payload
    assert "recvWindow" not in client.session.payload


@pytest.mark.asyncio
async def test_legacy_place_order_sends_receive_window_fields_when_supplied():
    client = LimitlessClient(private_key="0x" + "a" * 64)
    client.ensure_authenticated = AsyncMock()
    client.ensure_session = AsyncMock()
    client.session = _FakeSession()

    await client.place_order(
        _legacy_order_dto(timestamp=1_770_000_000_000, recvWindow=1500)
    )

    assert client.session.payload["timestamp"] == 1_770_000_000_000
    assert client.session.payload["recvWindow"] == 1500
    assert "timestamp" not in client.session.payload["order"]
    assert "recvWindow" not in client.session.payload["order"]
