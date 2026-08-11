"""Tests for the partner AMM trading service."""

import json
from unittest.mock import AsyncMock, Mock

import pytest

from limitless_sdk.api.errors import (
    AuthenticationError,
    ConflictError,
    RateLimitError,
    TooEarlyError,
    UnprocessableEntityError,
    UpstreamUnavailableError,
)
from limitless_sdk.api.http_client import HttpRawResponse
from limitless_sdk.partner_amm import PartnerAmmService
from limitless_sdk.types.partner_amm import (
    AmmAllowanceParams,
    AmmBuyParams,
    AmmSellParams,
)


HMAC_CREDS = {"token_id": "token-1", "secret": "secret-1"}


def _make_client(hmac=HMAC_CREDS):
    client = Mock()
    client.require_auth = Mock()
    client.get_hmac_credentials = Mock(return_value=hmac)
    client.post = AsyncMock()
    client.post_with_identity = AsyncMock()
    client.post_raw = AsyncMock()
    client.post_raw_with_identity = AsyncMock()
    return client


def _allowance_response(side="BUY", status="confirmed", confirmed=True, **overrides):
    data = {
        "status": status,
        "confirmed": confirmed,
        "market": "market-slug",
        "marketAddress": "0xmarket",
        "side": side,
        "walletAddress": "0xwallet",
        "tokenAddress": "0xtoken",
        "spenderOrOperator": "0xspender",
        "transactionId": "tx-1",
    }
    if side == "BUY":
        data["currentAllowance"] = "1000000"
    data.update(overrides)
    return data


def _buy_response(**overrides):
    data = {
        "status": "SUBMITTED",
        "market": "market-slug",
        "outcomeIndex": 0,
        "collateralAmount": "1000000",
        "expectedShares": "1900000",
        "minShares": "1800000",
        "transactionId": "tx-buy",
        "userOperationHash": "0xuserop",
    }
    data.update(overrides)
    return data


# --- 1. allowance mapping: BUY currentAllowance vs SELL omit -----------------

@pytest.mark.asyncio
async def test_check_allowance_buy_parses_current_allowance():
    client = _make_client()
    client.post.return_value = _allowance_response(side="BUY", status="confirmed")

    service = PartnerAmmService(client)
    result = await service.check_allowance(
        AmmAllowanceParams(market="market-slug", side="BUY")
    )

    client.post.assert_awaited_once_with(
        "/amm/allowances/check", {"market": "market-slug", "side": "BUY"}
    )
    assert result.current_allowance == "1000000"
    assert result.confirmed is True
    assert result.status == "confirmed"


@pytest.mark.asyncio
async def test_check_allowance_sell_omits_current_allowance():
    client = _make_client()
    client.post.return_value = _allowance_response(
        side="SELL", status="missing", confirmed=False
    )

    service = PartnerAmmService(client)
    result = await service.check_allowance(
        AmmAllowanceParams(market="market-slug", side="SELL")
    )

    assert result.current_allowance is None
    assert result.status == "missing"
    assert result.confirmed is False


# --- 2. approve 200/202 + ensure_allowance polls check, not approve ----------

@pytest.mark.asyncio
async def test_approve_allowance_returns_response():
    client = _make_client()
    client.post.return_value = _allowance_response(
        side="BUY", status="submitted", confirmed=False
    )

    service = PartnerAmmService(client)
    result = await service.approve_allowance(
        AmmAllowanceParams(market="market-slug", side="BUY")
    )

    client.post.assert_awaited_once_with(
        "/amm/allowances/approve", {"market": "market-slug", "side": "BUY"}
    )
    assert result.status == "submitted"


@pytest.mark.asyncio
async def test_ensure_allowance_returns_immediately_when_confirmed():
    client = _make_client()
    client.post.return_value = _allowance_response(side="BUY", confirmed=True)

    service = PartnerAmmService(client)
    result = await service.ensure_allowance(
        AmmAllowanceParams(market="market-slug", side="BUY")
    )

    # Only the initial check should have run (no approve, no poll).
    client.post.assert_awaited_once_with(
        "/amm/allowances/check", {"market": "market-slug", "side": "BUY"}
    )
    assert result.confirmed is True


@pytest.mark.asyncio
async def test_ensure_allowance_checks_then_approves_then_polls_check(monkeypatch):
    client = _make_client()
    # check(missing) -> approve(submitted) -> check(missing) -> check(confirmed)
    client.post.side_effect = [
        _allowance_response(side="BUY", status="missing", confirmed=False),
        _allowance_response(side="BUY", status="submitted", confirmed=False),
        _allowance_response(side="BUY", status="submitted", confirmed=False),
        _allowance_response(side="BUY", status="confirmed", confirmed=True),
    ]
    monkeypatch.setattr("asyncio.sleep", AsyncMock())

    service = PartnerAmmService(client)
    result = await service.ensure_allowance(
        AmmAllowanceParams(market="market-slug", side="BUY"), interval=0.01
    )

    paths = [call.args[0] for call in client.post.await_args_list]
    assert paths == [
        "/amm/allowances/check",
        "/amm/allowances/approve",
        "/amm/allowances/check",
        "/amm/allowances/check",
    ]
    # Only one approve, the rest are checks (never poll approve).
    assert paths.count("/amm/allowances/approve") == 1
    assert result.confirmed is True


# --- 3. buy/sell do not preflight check/approve ------------------------------

@pytest.mark.asyncio
async def test_buy_posts_exact_body_without_preflight():
    client = _make_client()
    client.post.return_value = _buy_response()

    service = PartnerAmmService(client)
    result = await service.buy(
        AmmBuyParams(
            market="market-slug",
            outcome_index=0,
            collateral_amount="1000000",
            idempotency_key="key-1",
        )
    )

    client.post.assert_awaited_once_with(
        "/amm/buy",
        {
            "market": "market-slug",
            "outcomeIndex": 0,
            "collateralAmount": "1000000",
            "idempotencyKey": "key-1",
        },
    )
    # No allowance endpoints touched.
    posted_paths = [call.args[0] for call in client.post.await_args_list]
    assert "/amm/allowances/check" not in posted_paths
    assert "/amm/allowances/approve" not in posted_paths
    assert result.status == "SUBMITTED"
    assert result.collateral_amount == "1000000"


@pytest.mark.asyncio
async def test_sell_posts_exact_body_with_slippage_and_on_behalf_of():
    client = _make_client()
    client.post.return_value = {
        "status": "SUBMITTED",
        "market": "market-slug",
        "outcomeIndex": 1,
        "collateralReturnAmount": "500000",
        "expectedShares": "480000",
        "maxShares": "520000",
    }

    service = PartnerAmmService(client)
    result = await service.sell(
        AmmSellParams(
            market="market-slug",
            outcome_index=1,
            collateral_return_amount="500000",
            slippage_bps=0,
            idempotency_key="key-2",
            on_behalf_of=42,
        )
    )

    client.post.assert_awaited_once_with(
        "/amm/sell",
        {
            "market": "market-slug",
            "outcomeIndex": 1,
            "collateralReturnAmount": "500000",
            "slippageBps": 0,
            "idempotencyKey": "key-2",
            "onBehalfOf": 42,
        },
    )
    assert result.collateral_return_amount == "500000"
    assert result.tx_hash is None


# --- 4. validation matrix (raise before network) -----------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params, match",
    [
        (
            AmmBuyParams(
                market="", outcome_index=0, collateral_amount="1", idempotency_key="k"
            ),
            "market is required",
        ),
        (
            AmmBuyParams(
                market="m", outcome_index=2, collateral_amount="1", idempotency_key="k"
            ),
            "outcome_index must be 0",
        ),
        (
            AmmBuyParams(
                market="m", outcome_index=0, collateral_amount="0", idempotency_key="k"
            ),
            "positive integer string",
        ),
        (
            AmmBuyParams(
                market="m", outcome_index=0, collateral_amount="01", idempotency_key="k"
            ),
            "positive integer string",
        ),
        (
            AmmBuyParams(
                market="m", outcome_index=0, collateral_amount="1.5", idempotency_key="k"
            ),
            "positive integer string",
        ),
        (
            AmmBuyParams(
                market="m",
                outcome_index=0,
                collateral_amount="1",
                slippage_bps=1001,
                idempotency_key="k",
            ),
            "slippage_bps must be between 0 and 1000",
        ),
        (
            AmmBuyParams(
                market="m", outcome_index=0, collateral_amount="1", idempotency_key="   "
            ),
            "idempotency_key is required",
        ),
        (
            AmmBuyParams(
                market="m",
                outcome_index=0,
                collateral_amount="1",
                idempotency_key="k",
                on_behalf_of=0,
            ),
            "on_behalf_of must be a positive",
        ),
    ],
)
async def test_buy_validation_rejects_before_network(params, match):
    client = _make_client()
    service = PartnerAmmService(client)

    with pytest.raises(ValueError, match=match):
        await service.buy(params)

    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_buy_rejects_amount_above_uint256():
    client = _make_client()
    service = PartnerAmmService(client)
    too_big = str((1 << 256))  # uint256 max + 1

    with pytest.raises(ValueError, match="positive integer string"):
        await service.buy(
            AmmBuyParams(
                market="m",
                outcome_index=0,
                collateral_amount=too_big,
                idempotency_key="k",
            )
        )

    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_allowance_rejects_bad_side():
    client = _make_client()
    service = PartnerAmmService(client)

    with pytest.raises(ValueError, match="side must be BUY or SELL"):
        await service.check_allowance(
            AmmAllowanceParams(market="m", side="buy")
        )

    client.post.assert_not_awaited()


# --- 5 & 6. idempotency: byte-identical retry; changed key -> conflict --------

@pytest.mark.asyncio
async def test_retry_sends_byte_identical_body():
    client = _make_client()
    client.post.return_value = _buy_response()

    service = PartnerAmmService(client)
    params = AmmBuyParams(
        market="market-slug",
        outcome_index=0,
        collateral_amount="1000000",
        idempotency_key="key-retry",
    )

    await service.buy(params)
    await service.buy(params)

    first_body = client.post.await_args_list[0].args[1]
    second_body = client.post.await_args_list[1].args[1]
    assert first_body == second_body
    assert json.dumps(first_body, separators=(",", ":")) == json.dumps(
        second_body, separators=(",", ":")
    )


@pytest.mark.asyncio
async def test_buy_conflict_maps_to_conflict_error():
    client = _make_client()
    client.post.side_effect = ConflictError("idempotency conflict", 409)

    service = PartnerAmmService(client)

    with pytest.raises(ConflictError):
        await service.buy(
            AmmBuyParams(
                market="m",
                outcome_index=0,
                collateral_amount="1",
                idempotency_key="k",
            )
        )


# --- 7. optional identifiers handled independently ---------------------------

@pytest.mark.asyncio
async def test_optional_identifiers_parse_independently():
    client = _make_client()
    client.post.return_value = _buy_response(
        transactionId=None, userOperationHash="0xonly-userop", txHash=None
    )

    service = PartnerAmmService(client)
    result = await service.buy(
        AmmBuyParams(
            market="m", outcome_index=0, collateral_amount="1", idempotency_key="k"
        )
    )

    assert result.transaction_id is None
    assert result.user_operation_hash == "0xonly-userop"
    assert result.tx_hash is None


# --- 8. onBehalfOf sent vs omitted -------------------------------------------

@pytest.mark.asyncio
async def test_on_behalf_of_omitted_for_direct_profile():
    client = _make_client()
    client.post.return_value = _allowance_response(side="BUY")

    service = PartnerAmmService(client)
    await service.check_allowance(AmmAllowanceParams(market="m", side="BUY"))

    body = client.post.await_args.args[1]
    assert "onBehalfOf" not in body


@pytest.mark.asyncio
async def test_on_behalf_of_sent_for_sub_account():
    client = _make_client()
    client.post.return_value = _allowance_response(side="BUY")

    service = PartnerAmmService(client)
    await service.check_allowance(
        AmmAllowanceParams(market="m", side="BUY", on_behalf_of=7)
    )

    body = client.post.await_args.args[1]
    assert body["onBehalfOf"] == 7


# --- 9. auth: identity vs HMAC + error mapping -------------------------------

@pytest.mark.asyncio
async def test_identity_auth_uses_identity_transport():
    client = _make_client(hmac=None)
    client.post_with_identity.return_value = _allowance_response(side="BUY")

    service = PartnerAmmService(client)
    result = await service.check_allowance(
        AmmAllowanceParams(market="m", side="BUY"), identity_token="privy-token"
    )

    client.post_with_identity.assert_awaited_once_with(
        "/amm/allowances/check", "privy-token", {"market": "m", "side": "BUY"}
    )
    client.post.assert_not_awaited()
    client.require_auth.assert_not_called()
    assert result.side == "BUY"


@pytest.mark.asyncio
async def test_hmac_auth_uses_default_transport_and_gates_legacy_key():
    client = _make_client(hmac=None)
    service = PartnerAmmService(client)

    with pytest.raises(ValueError, match="legacy API keys are not supported"):
        await service.buy(
            AmmBuyParams(
                market="m",
                outcome_index=0,
                collateral_amount="1",
                idempotency_key="k",
            )
        )

    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_identity_token_rejected():
    client = _make_client()
    service = PartnerAmmService(client)

    with pytest.raises(ValueError, match="identity_token is required"):
        await service.check_allowance(
            AmmAllowanceParams(market="m", side="BUY"), identity_token="   "
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        AuthenticationError("forbidden", 403),
        UnprocessableEntityError("insufficient balance", 422),
        TooEarlyError("maintenance", 425),
        RateLimitError("rate limited", 429),
        UpstreamUnavailableError("privy down", 502),
        UpstreamUnavailableError("redis down", 503),
    ],
)
async def test_error_mapping_propagates_typed_errors(error):
    client = _make_client()
    client.post.side_effect = error

    service = PartnerAmmService(client)

    with pytest.raises(type(error)):
        await service.buy(
            AmmBuyParams(
                market="m",
                outcome_index=0,
                collateral_amount="1",
                idempotency_key="k",
            )
        )


# --- raw-mode AMM assertions -------------------------------------------------

@pytest.mark.asyncio
async def test_buy_with_raw_response_returns_raw():
    client = _make_client()
    raw = HttpRawResponse(status=201, headers={"x-trace": "t"}, data=_buy_response())
    client.post_raw.return_value = raw

    service = PartnerAmmService(client)
    result = await service.buy(
        AmmBuyParams(
            market="market-slug",
            outcome_index=0,
            collateral_amount="1000000",
            idempotency_key="key-raw",
        ),
        with_raw_response=True,
    )

    assert isinstance(result, HttpRawResponse)
    assert result.status == 201
    assert result.headers["x-trace"] == "t"
    assert result.data["status"] == "SUBMITTED"
    client.post_raw.assert_awaited_once_with(
        "/amm/buy",
        {
            "market": "market-slug",
            "outcomeIndex": 0,
            "collateralAmount": "1000000",
            "idempotencyKey": "key-raw",
        },
    )
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_allowance_with_raw_response_and_identity():
    client = _make_client(hmac=None)
    raw = HttpRawResponse(status=200, headers={}, data=_allowance_response(side="BUY"))
    client.post_raw_with_identity.return_value = raw

    service = PartnerAmmService(client)
    result = await service.check_allowance(
        AmmAllowanceParams(market="m", side="BUY"),
        identity_token="privy-token",
        with_raw_response=True,
    )

    assert isinstance(result, HttpRawResponse)
    assert result.status == 200
    client.post_raw_with_identity.assert_awaited_once_with(
        "/amm/allowances/check", "privy-token", {"market": "m", "side": "BUY"}
    )
