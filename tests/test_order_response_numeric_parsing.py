"""Tests for create_order numeric string parsing in order response models."""

import pytest
from pydantic import ValidationError

from limitless_sdk.types.orders import OrderResponse


def _base_order_payload() -> dict:
    return {
        "id": "order-1",
        "createdAt": "2026-03-16T00:00:00.000Z",
        "salt": "9007199254740993",
        "maker": "0x0000000000000000000000000000000000000001",
        "signer": "0x0000000000000000000000000000000000000001",
        "taker": "0x0000000000000000000000000000000000000000",
        "tokenId": "123",
        "makerAmount": "50000000",
        "takerAmount": "100000000",
        "expiration": "0",
        "nonce": 0,
        "feeRateBps": 300,
        "side": 0,
        "signatureType": 0,
        "price": "0.52",
        "signature": "0x" + "a" * 130,
    }


def test_order_response_parses_numeric_strings_for_create_order_payload_fields() -> None:
    response = OrderResponse(
        order=_base_order_payload(),
        makerMatches=[],
    )

    assert response.order.maker_amount == 50_000_000
    assert response.order.taker_amount == 100_000_000
    assert response.order.price == 0.52
    assert response.order.salt == 9_007_199_254_740_993


def test_order_response_rejects_invalid_salt_string() -> None:
    payload = _base_order_payload()
    payload["salt"] = "not-a-number"

    with pytest.raises(ValidationError):
        OrderResponse(order=payload, makerMatches=[])


def test_order_response_rejects_boolean_maker_amount() -> None:
    payload = _base_order_payload()
    payload["makerAmount"] = True

    with pytest.raises(ValidationError):
        OrderResponse(order=payload, makerMatches=[])


def test_order_response_rejects_non_finite_price() -> None:
    payload = _base_order_payload()
    payload["price"] = "inf"

    with pytest.raises(ValidationError):
        OrderResponse(order=payload, makerMatches=[])


def test_order_response_rejects_unsafe_float_integer_for_salt() -> None:
    payload = _base_order_payload()
    payload["salt"] = float(9_007_199_254_740_993)

    with pytest.raises(ValidationError):
        OrderResponse(order=payload, makerMatches=[])


def test_order_response_rejects_large_integer_like_price_string() -> None:
    payload = _base_order_payload()
    payload["price"] = "9007199254740993"

    with pytest.raises(ValidationError):
        OrderResponse(order=payload, makerMatches=[])


def test_order_response_accepts_null_created_at_in_maker_matches() -> None:
    response = OrderResponse(
        order=_base_order_payload(),
        makerMatches=[
            {
                "id": "e6ef7cf5-d43b-4927-80d1-23f34feb48d3",
                "createdAt": None,
                "matchedSize": "1000000",
                "orderId": "2c92ce01-e59b-4966-9d3f-a03bdb85e3eb",
            }
        ],
    )

    assert response.maker_matches is not None
    assert len(response.maker_matches) == 1
    assert response.maker_matches[0].created_at is None
    assert response.maker_matches[0].matched_size == "1000000"


def _execution_payload() -> dict:
    return {
        "matched": True,
        "settlementStatus": "MATCHED",
        "tradeEventId": "9f7e6d5c-4b3a-2918-0716-5a4b3c2d1e0f",
        "txHash": None,
        "feeRateBps": 300,
        "effectiveFeeBps": 0,
        "totalsRaw": {
            "contractsGross": "5000000",
            "contractsFee": "0",
            "contractsNet": "5000000",
            "usdGross": "2250000",
            "usdFee": "0",
            "usdNet": "2250000",
        },
    }


def test_order_response_surfaces_execution_with_typed_fields() -> None:
    response = OrderResponse(
        order=_base_order_payload(),
        makerMatches=[],
        execution=_execution_payload(),
    )

    assert response.execution is not None
    execution = response.execution
    assert execution.matched is True
    # settlementStatus is a plain string, not coerced to any enum
    assert execution.settlement_status == "MATCHED"
    # fee fields are numbers
    assert execution.fee_rate_bps == 300
    assert execution.effective_fee_bps == 0
    # totalsRaw fields stay strings (not coerced to numbers)
    assert execution.totals_raw.usd_net == "2250000"
    assert execution.totals_raw.contracts_gross == "5000000"
    assert isinstance(execution.totals_raw.usd_net, str)
    # optionals default to None when absent
    assert execution.reason is None
    assert execution.stp_maker_cancels is None


def test_order_response_execution_carries_stp_signals() -> None:
    payload = _execution_payload()
    payload["matched"] = False
    payload["settlementStatus"] = "CANCELED"
    payload["reason"] = "STP_TAKER_REJECTED"
    payload["stpMakerCancels"] = [
        "2c92ce01-e59b-4966-9d3f-a03bdb85e3eb",
        "e6ef7cf5-d43b-4927-80d1-23f34feb48d3",
    ]

    response = OrderResponse(
        order=_base_order_payload(),
        makerMatches=[],
        execution=payload,
    )

    assert response.execution is not None
    assert response.execution.reason == "STP_TAKER_REJECTED"
    assert response.execution.stp_maker_cancels == [
        "2c92ce01-e59b-4966-9d3f-a03bdb85e3eb",
        "e6ef7cf5-d43b-4927-80d1-23f34feb48d3",
    ]
    # stp_maker_cancels entries stay strings
    assert all(isinstance(uid, str) for uid in response.execution.stp_maker_cancels)


def test_order_response_tolerates_missing_execution() -> None:
    response = OrderResponse(
        order=_base_order_payload(),
        makerMatches=[],
    )

    assert response.execution is None
