"""Tests for collateral fee venue detection and order fee rates."""

from unittest.mock import AsyncMock, Mock

import pytest
from eth_account import Account

from limitless_sdk import (
    FEE_MODULE_TYPE_COLLATERAL,
    Client,
    LimitlessClient,
    is_collateral_fee_venue,
)
from limitless_sdk.delegated_orders import DelegatedOrderService
from limitless_sdk.orders import OrderClient
from limitless_sdk.orders.builder import OrderBuilder, apply_venue_fee_rate
from limitless_sdk.types import OrderType, Side, UserData, Venue

EXCHANGE = "0x" + "1" * 40
ADAPTER = "0x" + "2" * 40
FEE_MODULE = "0x" + "3" * 40
PROFILE_FEE_RATE_BPS = 300

LEGACY_VENUE = Venue(exchange=EXCHANGE, adapter=None)
COLLATERAL_VENUE = Venue(
    exchange=EXCHANGE,
    adapter=None,
    feeModule=FEE_MODULE,
    feeModuleType=FEE_MODULE_TYPE_COLLATERAL,
)


def _market_fetcher(venue):
    market_fetcher = Mock()
    market_fetcher.get_venue.return_value = venue
    return market_fetcher


def _cancel_replace_result():
    return {
        "cancel": {"status": "FAILURE", "error": {"code": "X", "message": "x"}},
        "replacement": {"status": "NOT_ATTEMPTED"},
    }


def _order_client(http, venue):
    wallet = Account.from_key("0x" + "a" * 64)
    client = OrderClient(http, wallet, market_fetcher=_market_fetcher(venue))
    client._cached_user_data = UserData(user_id=7, fee_rate_bps=PROFILE_FEE_RATE_BPS)
    client._builder = OrderBuilder(wallet.address, PROFILE_FEE_RATE_BPS)
    client._signer.sign_order = AsyncMock(return_value="0x" + "a" * 130)
    return client


@pytest.fixture(autouse=True)
def _fixed_salt(monkeypatch):
    monkeypatch.setattr(
        "limitless_sdk.orders.builder.OrderBuilder._generate_salt", lambda self: 123
    )


# --- detection -------------------------------------------------------------


def test_is_collateral_fee_venue_detects_new_and_legacy_venues():
    assert is_collateral_fee_venue(COLLATERAL_VENUE) is True
    assert is_collateral_fee_venue(LEGACY_VENUE) is False
    assert is_collateral_fee_venue(None) is False
    assert (
        is_collateral_fee_venue(Venue(exchange=EXCHANGE, feeModuleType="OTHER"))
        is False
    )


def test_venue_parses_fee_module_fields_when_present():
    venue = Venue.model_validate(
        {
            "exchange": EXCHANGE,
            "adapter": ADAPTER,
            "feeModule": FEE_MODULE,
            "feeModuleType": "COLLATERAL",
        }
    )

    assert venue.fee_module == FEE_MODULE
    assert venue.fee_module_type == "COLLATERAL"
    assert is_collateral_fee_venue(venue)


def test_venue_parses_legacy_payload_without_fee_module_fields():
    venue = Venue.model_validate({"exchange": EXCHANGE, "adapter": None})

    assert venue.fee_module is None
    assert venue.fee_module_type is None
    assert not is_collateral_fee_venue(venue)


def test_apply_venue_fee_rate_only_changes_collateral_fee_venues():
    order = OrderBuilder(EXCHANGE, PROFILE_FEE_RATE_BPS).build_order(
        token_id="123", price=0.5, size=2.0, side=Side.BUY
    )

    assert apply_venue_fee_rate(order, LEGACY_VENUE) is order
    assert apply_venue_fee_rate(order, None) is order
    assert apply_venue_fee_rate(order, COLLATERAL_VENUE).fee_rate_bps == 0
    assert order.fee_rate_bps == PROFILE_FEE_RATE_BPS


# --- order client ------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("venue", "expected_fee_rate_bps"),
    [(COLLATERAL_VENUE, 0), (LEGACY_VENUE, PROFILE_FEE_RATE_BPS)],
)
async def test_create_order_signs_fee_rate_for_venue(venue, expected_fee_rate_bps):
    http = Mock()
    http.post_raw = AsyncMock(return_value=Mock())
    client = _order_client(http, venue)

    await client.create_order(
        token_id="123",
        side=Side.SELL,
        order_type=OrderType.GTC,
        market_slug="market",
        price=0.5,
        size=2.0,
        with_raw_response=True,
    )

    signed_order, signing_config = client._signer.sign_order.await_args.args
    assert signed_order.fee_rate_bps == expected_fee_rate_bps
    assert signing_config.contract_address == EXCHANGE
    _, payload = http.post_raw.await_args.args
    assert payload["order"]["feeRateBps"] == expected_fee_rate_bps


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("venue", "expected_fee_rate_bps"),
    [(COLLATERAL_VENUE, 0), (LEGACY_VENUE, PROFILE_FEE_RATE_BPS)],
)
async def test_cancel_replace_signs_fee_rate_for_venue(venue, expected_fee_rate_bps):
    http = Mock()
    http.post = AsyncMock(return_value=_cancel_replace_result())
    client = _order_client(http, venue)

    await client.cancel_replace(
        order_id="old-order",
        token_id="123",
        side=Side.BUY,
        order_type=OrderType.FOK,
        market_slug="market",
        maker_amount=5.0,
    )

    signed_order = client._signer.sign_order.await_args.args[0]
    assert signed_order.fee_rate_bps == expected_fee_rate_bps
    _, payload = http.post.await_args.args
    assert payload["replacement"]["order"]["feeRateBps"] == expected_fee_rate_bps


# --- delegated orders ----------------------------------------------------------


def _delegated_http():
    http = Mock()
    http.require_auth = Mock()
    http.post_raw = AsyncMock(return_value=Mock())
    http.post = AsyncMock(return_value=_cancel_replace_result())
    return http


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("venue", "fee_rate_bps", "expected_fee_rate_bps"),
    [
        (COLLATERAL_VENUE, None, 0),
        (COLLATERAL_VENUE, 250, 0),
        (LEGACY_VENUE, None, 300),
        (LEGACY_VENUE, 250, 250),
    ],
)
async def test_delegated_create_order_uses_venue_fee_rate(
    venue, fee_rate_bps, expected_fee_rate_bps
):
    http = _delegated_http()
    service = DelegatedOrderService(http, market_fetcher=_market_fetcher(venue))

    await service.create_order(
        token_id="123",
        side=Side.BUY,
        order_type=OrderType.GTC,
        market_slug="market",
        on_behalf_of=326,
        price=0.5,
        size=2.0,
        fee_rate_bps=fee_rate_bps,
        with_raw_response=True,
    )

    _, payload = http.post_raw.await_args.args
    assert payload["order"]["feeRateBps"] == expected_fee_rate_bps


@pytest.mark.asyncio
async def test_delegated_create_order_fetches_market_when_venue_not_cached():
    http = _delegated_http()
    market_fetcher = _market_fetcher(None)
    market_fetcher.get_market = AsyncMock(return_value=Mock(venue=COLLATERAL_VENUE))
    service = DelegatedOrderService(http, market_fetcher=market_fetcher)

    await service.create_order(
        token_id="123",
        side=Side.SELL,
        order_type=OrderType.FOK,
        market_slug="market",
        on_behalf_of=326,
        maker_amount=5.0,
        with_raw_response=True,
    )

    market_fetcher.get_market.assert_awaited_once_with("market")
    _, payload = http.post_raw.await_args.args
    assert payload["order"]["feeRateBps"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("venue", "expected_fee_rate_bps"),
    [(COLLATERAL_VENUE, 0), (LEGACY_VENUE, 300)],
)
async def test_delegated_cancel_replace_uses_venue_fee_rate(venue, expected_fee_rate_bps):
    http = _delegated_http()
    service = DelegatedOrderService(http, market_fetcher=_market_fetcher(venue))

    await service.cancel_replace(
        order_id="old-order",
        token_id="123",
        side=Side.BUY,
        order_type=OrderType.GTC,
        market_slug="market",
        price=0.5,
        size=2.0,
        on_behalf_of=7,
    )

    _, payload = http.post.await_args.args
    assert payload["replacement"]["order"]["feeRateBps"] == expected_fee_rate_bps


def test_root_client_shares_market_fetcher_with_delegated_orders():
    client = Client(api_key="lmts_test")

    assert client.delegated_orders._market_fetcher is client.markets


# --- legacy client -------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("venue", "expected_fee_rate_bps"),
    [
        ({"exchange": EXCHANGE, "feeModule": FEE_MODULE, "feeModuleType": "COLLATERAL"}, 0),
        ({"exchange": EXCHANGE, "adapter": None}, 300),
    ],
)
async def test_legacy_client_create_order_uses_venue_fee_rate(venue, expected_fee_rate_bps):
    client = LimitlessClient(private_key="0x" + "a" * 64)
    client.get_user_profile = AsyncMock(return_value={"id": 7})
    client._get_token_id_for_market = AsyncMock(return_value="123")
    client.get_market = AsyncMock(return_value={"venue": venue})
    client._calculate_amounts = AsyncMock(return_value=("1000000", "2000000"))
    client._sign_order = Mock(return_value="0x" + "a" * 130)

    dto = await client.create_order(
        market_id="1",
        market_slug="market",
        outcome_index=0,
        side=0,
        amount=1.0,
        price=0.5,
    )

    assert dto.order.feeRateBps == expected_fee_rate_bps
