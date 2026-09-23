from unittest.mock import AsyncMock, Mock

import pytest
from eth_account import Account

from limitless_sdk.api import APIError, ValidationError
from limitless_sdk.api.http_client import HttpRawResponse
from limitless_sdk.orders import OrderClient
from limitless_sdk.orders.builder import OrderBuilder
from limitless_sdk.types import OrderType, Side, UserData, UserProfile

WALLET = Account.from_key("0x" + "a" * 64)
SIGNATURE = "0x" + "a" * 130


def _client():
    http = Mock()
    market_fetcher = Mock()
    market_fetcher.get_venue.return_value = Mock(
        exchange="0x" + "1" * 40,
        adapter="0x" + "2" * 40,
    )
    client = OrderClient(http, WALLET, market_fetcher=market_fetcher)
    client._cached_user_data = UserData(user_id=7, fee_rate_bps=300)
    client._builder = OrderBuilder(WALLET.address, 300)
    client._signer.sign_order = AsyncMock(return_value=SIGNATURE)
    return client, http


def _profile(**values):
    return UserProfile(
        id=7,
        account=WALLET.address,
        client="sdk",
        rank={"id": 1, "name": "rank", "feeRateBps": 300},
        **values,
    )


def _order_args():
    return {
        "token_id": "123",
        "side": Side.BUY,
        "order_type": OrderType.GTC,
        "market_slug": "market",
        "price": 0.5,
        "size": 2.0,
    }


@pytest.mark.parametrize("effective_fee", [150, 0])
def test_profile_effective_fee_beats_rank(effective_fee):
    assert _profile(effectiveFeeRateBps=effective_fee).fee_rate_bps == effective_fee


@pytest.mark.parametrize("effective_fee", [True, "150", None])
def test_profile_invalid_effective_fee_falls_back_to_rank(effective_fee):
    assert _profile(effectiveFeeRateBps=effective_fee).fee_rate_bps == 300


@pytest.mark.asyncio
async def test_order_client_caches_top_level_effective_fee(monkeypatch):
    client, _ = _client()
    client._cached_user_data = None
    client._builder = None
    monkeypatch.setattr(
        "limitless_sdk.orders.client.PortfolioFetcher.get_profile",
        AsyncMock(
            return_value={
                "id": 7,
                "account": WALLET.address,
                "effectiveFeeRateBps": 0,
                "rank": {"feeRateBps": 300},
            }
        ),
    )

    user_data = await client._ensure_user_data()

    assert user_data.fee_rate_bps == 0
    assert client._builder.fee_rate_bps == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("with_raw_response", [False, True])
async def test_fee_mismatch_rebuilds_resigns_and_reposts_once(
    monkeypatch, with_raw_response
):
    client, http = _client()
    build_fees = []
    original_build = OrderBuilder.build_order

    def record_build(builder, *args, **kwargs):
        build_fees.append(builder.fee_rate_bps)
        return original_build(builder, *args, **kwargs)

    monkeypatch.setattr(OrderBuilder, "build_order", record_build)
    mismatch = ValidationError(
        "fee mismatch",
        status_code=400,
        response_data={
            "code": "FEE_RATE_MISMATCH",
            "expectedFeeRateBps": 150,
        },
    )

    if with_raw_response:
        http.post_raw = AsyncMock(
            side_effect=[
                mismatch,
                HttpRawResponse(status=201, headers={}, data={"ok": True}),
            ]
        )
    else:

        async def post(_path, payload):
            if http.post.await_count == 1:
                raise mismatch
            order = dict(payload["order"])
            order["id"] = "order-id"
            return {"order": order, "makerMatches": []}

        http.post = AsyncMock(side_effect=post)

    await client.create_order(**_order_args(), with_raw_response=with_raw_response)

    post = http.post_raw if with_raw_response else http.post
    assert post.await_count == 2
    assert client._signer.sign_order.await_count == 2
    assert build_fees == [300, 150]
    assert [call.args[1]["order"]["feeRateBps"] for call in post.await_args_list] == [
        300,
        150,
    ]
    assert client._cached_user_data.fee_rate_bps == 300
    assert client._builder.fee_rate_bps == 300


@pytest.mark.asyncio
async def test_market_retry_fee_does_not_change_later_create_or_cancel_replace():
    client, http = _client()
    mismatch = ValidationError(
        "fee mismatch",
        status_code=400,
        response_data={
            "code": "FEE_RATE_MISMATCH",
            "expectedFeeRateBps": 0,
        },
    )
    create_payloads = []
    cancel_replace_payload = None

    async def post(path, payload, **_kwargs):
        nonlocal cancel_replace_payload
        if path == "/orders":
            create_payloads.append(payload)
            if len(create_payloads) == 1:
                raise mismatch
            order = dict(payload["order"])
            order["id"] = f"order-{len(create_payloads)}"
            return {"order": order, "makerMatches": []}
        cancel_replace_payload = payload
        return {
            "cancel": {
                "status": "FAILURE",
                "error": {"code": "X", "message": "x"},
            },
            "replacement": {"status": "NOT_ATTEMPTED"},
        }

    http.post = AsyncMock(side_effect=post)

    await client.create_order(**{**_order_args(), "market_slug": "fee-disabled"})
    await client.create_order(**{**_order_args(), "market_slug": "fee-enabled"})
    await client.cancel_replace(
        order_id="old-order",
        **{**_order_args(), "market_slug": "fee-enabled"},
    )

    assert [payload["order"]["feeRateBps"] for payload in create_payloads] == [
        300,
        0,
        300,
    ]
    assert cancel_replace_payload["replacement"]["order"]["feeRateBps"] == 300
    assert client._cached_user_data.fee_rate_bps == 300
    assert client._builder.fee_rate_bps == 300


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("unknown outcome"),
        APIError(
            "server error",
            500,
            {"code": "FEE_RATE_MISMATCH", "expectedFeeRateBps": 150},
        ),
        ValidationError(
            "unknown mismatch",
            400,
            {"code": "FEE_RATE_MISMATCH", "expectedFeeRateBps": True},
        ),
        ValidationError(
            "other validation",
            400,
            {"code": "OTHER", "expectedFeeRateBps": 150},
        ),
    ],
)
async def test_create_order_does_not_retry_unknown_or_unapproved_errors(error):
    client, http = _client()
    http.post = AsyncMock(side_effect=error)

    with pytest.raises(type(error)):
        await client.create_order(**_order_args())

    assert http.post.await_count == 1
    assert client._signer.sign_order.await_count == 1
