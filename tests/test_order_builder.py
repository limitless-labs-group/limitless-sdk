import pytest

from limitless_sdk.orders.builder import OrderBuilder
from limitless_sdk.types import Side


@pytest.fixture
def order_builder() -> OrderBuilder:
    return OrderBuilder(
        maker_address="0x" + "1" * 40,
        fee_rate_bps=300,
        price_tick=0.001,
    )


def test_build_order_rejects_price_that_rounds_to_zero(order_builder: OrderBuilder) -> None:
    with pytest.raises(ValueError, match="rounds to 0.0"):
        order_builder.build_order(
            token_id="123",
            price=0.0001,
            size=1.0,
            side=Side.BUY,
        )


def test_build_order_accepts_min_tick_price(order_builder: OrderBuilder) -> None:
    order = order_builder.build_order(
        token_id="123",
        price=0.001,
        size=1.0,
        side=Side.BUY,
    )

    assert order.price == 0.001
    assert order.maker_amount > 0

