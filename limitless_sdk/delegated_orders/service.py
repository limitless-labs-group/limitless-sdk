"""Delegated-order service."""

from typing import Optional
from urllib.parse import quote

from ..api.http_client import HttpClient
from ..orders.builder import OrderBuilder
from ..types.delegated_orders import (
    CancelResponse,
    CreateDelegatedOrderRequest,
    DelegatedOrderSubmission,
)
from ..types.logger import ILogger, NoOpLogger
from ..types.orders import OrderResponse, OrderType, Side
from ..utils.constants import ZERO_ADDRESS


DEFAULT_DELEGATED_FEE_RATE_BPS = 300


class DelegatedOrderService:
    """Delegated partner-order operations."""

    def __init__(self, http_client: HttpClient, logger: Optional[ILogger] = None):
        self._http_client = http_client
        self._logger = logger or NoOpLogger()

    async def create_order(
        self,
        token_id: str,
        side: Side,
        order_type: OrderType,
        market_slug: str,
        on_behalf_of: int,
        price: Optional[float] = None,
        size: Optional[float] = None,
        maker_amount: Optional[float] = None,
        expiration: Optional[int] = None,
        taker: Optional[str] = None,
        fee_rate_bps: Optional[int] = None,
    ) -> OrderResponse:
        self._http_client.require_auth("create_delegated_order")

        if not isinstance(on_behalf_of, int) or on_behalf_of <= 0:
            raise ValueError("on_behalf_of must be a positive integer")

        effective_fee_rate_bps = (
            fee_rate_bps
            if isinstance(fee_rate_bps, int) and fee_rate_bps > 0
            else DEFAULT_DELEGATED_FEE_RATE_BPS
        )

        builder = OrderBuilder(ZERO_ADDRESS, effective_fee_rate_bps)

        if order_type == OrderType.FOK:
            if maker_amount is None:
                raise ValueError("FOK orders require maker_amount")
            unsigned_order = builder.build_fok_order(
                token_id=token_id,
                side=side,
                maker_amount=maker_amount,
                expiration=expiration,
                taker=taker,
            )
        else:
            if price is None or size is None:
                raise ValueError("GTC orders require price and size")
            unsigned_order = builder.build_order(
                token_id=token_id,
                price=price,
                size=size,
                side=side,
                expiration=expiration,
                taker=taker,
            )

        submission = DelegatedOrderSubmission(
            **{
                **unsigned_order.model_dump(by_alias=True, exclude_none=True),
                "expiration": str(unsigned_order.expiration),
            }
        )
        payload = CreateDelegatedOrderRequest(
            order=submission,
            order_type=order_type.value,
            market_slug=market_slug,
            owner_id=on_behalf_of,
            on_behalf_of=on_behalf_of,
        )

        self._logger.debug(
            "Creating delegated order",
            {
                "market_slug": market_slug,
                "on_behalf_of": on_behalf_of,
                "fee_rate_bps": effective_fee_rate_bps,
            },
        )

        response = await self._http_client.post(
            "/orders",
            payload.model_dump(by_alias=True, exclude_none=True),
        )
        return OrderResponse(**response)

    async def cancel(self, order_id: str) -> str:
        self._http_client.require_auth("cancel_delegated_order")
        response = CancelResponse(
            **await self._http_client.delete(f"/orders/{quote(order_id, safe='')}")
        )
        return response.message

    async def cancel_on_behalf_of(self, order_id: str, on_behalf_of: int) -> str:
        self._http_client.require_auth("cancel_delegated_order")
        if not isinstance(on_behalf_of, int) or on_behalf_of <= 0:
            raise ValueError("on_behalf_of must be a positive integer")

        response = CancelResponse(
            **await self._http_client.delete(
                f"/orders/{quote(order_id, safe='')}",
                params={"onBehalfOf": on_behalf_of},
            )
        )
        return response.message

    async def cancel_all(self, market_slug: str) -> str:
        self._http_client.require_auth("cancel_all_delegated_orders")
        response = CancelResponse(
            **await self._http_client.delete(
                f"/orders/all/{quote(market_slug, safe='')}"
            )
        )
        return response.message

    async def cancel_all_on_behalf_of(
        self,
        market_slug: str,
        on_behalf_of: int,
    ) -> str:
        self._http_client.require_auth("cancel_all_delegated_orders")
        if not isinstance(on_behalf_of, int) or on_behalf_of <= 0:
            raise ValueError("on_behalf_of must be a positive integer")

        response = CancelResponse(
            **await self._http_client.delete(
                f"/orders/all/{quote(market_slug, safe='')}",
                params={"onBehalfOf": on_behalf_of},
            )
        )
        return response.message
