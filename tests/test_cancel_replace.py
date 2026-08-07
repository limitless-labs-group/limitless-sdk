from unittest.mock import AsyncMock, Mock

import pytest
from eth_account import Account
from pydantic import ValidationError as PydanticValidationError

from limitless_sdk.api import ValidationError
from limitless_sdk.api.http_client import HttpClient
from limitless_sdk.delegated_orders import DelegatedOrderService
from limitless_sdk.orders import OrderClient
from limitless_sdk.orders.builder import OrderBuilder
from limitless_sdk.types import (
    CancelReplaceTarget,
    OrderType,
    Side,
    StpPolicy,
    UserData,
)


def _result(status="NOT_ATTEMPTED"):
    return {
        "cancel": {"status": "FAILURE", "error": {"code": "X", "message": "x"}},
        "replacement": {"status": status},
    }


def _operation(**values):
    return {
        "order_id": "old-order",
        "token_id": "123",
        "side": Side.BUY,
        "order_type": OrderType.GTC,
        "market_slug": "market",
        "price": 0.5,
        "size": 2.0,
        **values,
    }


def test_cancel_target_requires_exactly_one_identifier():
    with pytest.raises(PydanticValidationError):
        CancelReplaceTarget()
    with pytest.raises(PydanticValidationError):
        CancelReplaceTarget(order_id="one", client_order_id="two")
    assert CancelReplaceTarget(client_order_id="one").client_order_id == "one"


@pytest.mark.asyncio
async def test_delegated_cancel_replace_payload_casing_and_omissions(monkeypatch):
    http = Mock()
    http.require_auth = Mock()
    http.post = AsyncMock(return_value=_result())
    service = DelegatedOrderService(http)
    monkeypatch.setattr(
        "limitless_sdk.orders.builder.OrderBuilder._generate_salt", lambda self: 123
    )

    await service.cancel_replace(
        **_operation(
            on_behalf_of=7,
            replacement_client_order_id="new-client",
            timestamp=1000,
            recv_window=500,
            stp_policy=StpPolicy.CANCEL_TAKER,
        )
    )

    path, payload = http.post.await_args.args
    assert path == "/orders/cancel-replace"
    assert http.post.await_args.kwargs == {"accepted_statuses": {409}}
    assert payload["cancel"] == {"orderId": "old-order"}
    assert payload["onBehalfOf"] == 7
    assert "onBehalfOf" not in payload["replacement"]
    assert payload["replacement"]["clientOrderId"] == "new-client"
    assert payload["replacement"]["recvWindow"] == 500
    assert payload["replacement"]["stpPolicy"] == "cancel_taker"
    assert "signature" not in payload["replacement"]["order"]
    assert payload["replacement"]["order"]["expiration"] == "0"


@pytest.mark.asyncio
async def test_delegated_batch_uses_batch_path_and_has_no_client_max(monkeypatch):
    http = Mock()
    http.require_auth = Mock()
    http.post = AsyncMock(
        return_value={"results": [{"index": i, **_result()} for i in range(5)]}
    )
    service = DelegatedOrderService(http)
    monkeypatch.setattr(
        "limitless_sdk.orders.builder.OrderBuilder._generate_salt", lambda self: 123
    )
    response = await service.cancel_replace_batch(
        [_operation(on_behalf_of=7, order_id=f"old-{i}") for i in range(5)]
    )
    assert http.post.await_args.args[0] == "/orders/cancel-replace/batch"
    assert len(http.post.await_args.args[1]["operations"]) == 5
    assert response.results[4].index == 4


@pytest.mark.asyncio
async def test_direct_cancel_replace_signs_with_market_venue(monkeypatch):
    http = Mock()
    http.post = AsyncMock(return_value=_result())
    market_fetcher = Mock()
    venue = Mock(exchange="0x" + "1" * 40, adapter="0x" + "2" * 40)
    market_fetcher.get_venue.return_value = venue
    wallet = Account.from_key("0x" + "a" * 64)
    client = OrderClient(http, wallet, market_fetcher=market_fetcher)
    client._cached_user_data = UserData(user_id=7, fee_rate_bps=300)
    client._builder = OrderBuilder(wallet.address, 300)
    client._signer.sign_order = AsyncMock(return_value="0x" + "a" * 130)
    monkeypatch.setattr(
        "limitless_sdk.orders.builder.OrderBuilder._generate_salt", lambda self: 123
    )

    await client.cancel_replace(**_operation())

    signing_config = client._signer.sign_order.await_args.args[1]
    assert signing_config.contract_address == venue.exchange
    path, payload = http.post.await_args.args
    assert path == "/orders/cancel-replace"
    assert payload["replacement"]["order"]["signature"].startswith("0x")


class _Response:
    def __init__(self, status, data):
        self.status = status
        self.data = data
        self.headers = {}

    async def json(self):
        return self.data

    async def text(self):
        return str(self.data)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _Session:
    closed = False

    def __init__(self, response):
        self.response = response

    def post(self, *args, **kwargs):
        return self.response


@pytest.mark.asyncio
async def test_http_post_accepts_409_only_when_requested():
    client = HttpClient(api_key="key")
    client._session = _Session(_Response(409, _result()))
    assert await client.post("/orders/cancel-replace", {}, accepted_statuses={409}) == _result()

    client._session = _Session(_Response(400, {"message": "bad"}))
    with pytest.raises(ValidationError):
        await client.post("/orders/cancel-replace", {}, accepted_statuses={409})


@pytest.mark.asyncio
async def test_http_post_decodes_207():
    client = HttpClient(api_key="key")
    payload = {"results": [{"index": 0, **_result()}]}
    client._session = _Session(_Response(207, payload))
    assert await client.post("/orders/cancel-replace/batch", {}) == payload
