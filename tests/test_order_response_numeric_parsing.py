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
