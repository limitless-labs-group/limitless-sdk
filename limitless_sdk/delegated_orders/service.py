"""Delegated-order service."""

from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote

from ..api.http_client import HttpClient, HttpRawResponse
from ..orders.builder import OrderBuilder
from ..types.delegated_orders import (
    CancelResponse,
    CreateDelegatedOrderRequest,
    DelegatedOrderSubmission,
)
from ..types.logger import ILogger, NoOpLogger
from ..types.orders import (
    CancelReplaceBatchRequest,
    CancelReplaceBatchResponse,
    CancelReplaceMode,
    CancelReplaceOrderRequest,
    CancelReplaceOrderSubmission,
    CancelReplaceRequest,
    CancelReplaceResponse,
    CancelReplaceTarget,
    OrderResponse,
    OrderType,
    Side,
)
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
        post_only: Optional[bool] = None,
        with_raw_response: bool = False,
    ) -> Union[OrderResponse, HttpRawResponse]:
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
                raise ValueError(
                    f"{order_type.value} orders require price and size"
                )
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
            post_only=post_only if order_type == OrderType.GTC else None,
        )

        self._logger.debug(
            "Creating delegated order",
            {
                "market_slug": market_slug,
                "on_behalf_of": on_behalf_of,
                "fee_rate_bps": effective_fee_rate_bps,
            },
        )

        body = payload.model_dump(by_alias=True, exclude_none=True)
        if with_raw_response:
            return await self._http_client.post_raw("/orders", body)
        response = await self._http_client.post("/orders", body)
        return OrderResponse(**response)

    async def cancel(
        self, order_id: str, with_raw_response: bool = False
    ) -> Union[str, HttpRawResponse]:
        self._http_client.require_auth("cancel_delegated_order")
        path = f"/orders/{quote(order_id, safe='')}"
        if with_raw_response:
            return await self._http_client.delete_raw(path)
        response = CancelResponse(**await self._http_client.delete(path))
        return response.message

    async def _build_cancel_replace_request(
        self, **operation: Any
    ) -> CancelReplaceRequest:
        order_id = operation.pop("order_id", None)
        client_order_id = operation.pop("client_order_id", None)
        replacement_client_order_id = operation.pop(
            "replacement_client_order_id", None
        )
        mode = operation.pop("mode", CancelReplaceMode.STOP_ON_FAILURE)
        on_behalf_of = operation.pop("on_behalf_of")
        if not isinstance(on_behalf_of, int) or on_behalf_of <= 0:
            raise ValueError("on_behalf_of must be a positive integer")

        fee_rate_bps = operation.pop("fee_rate_bps", None)
        effective_fee_rate_bps = (
            fee_rate_bps
            if isinstance(fee_rate_bps, int) and fee_rate_bps > 0
            else DEFAULT_DELEGATED_FEE_RATE_BPS
        )
        order_type = operation.pop("order_type")
        token_id = operation.pop("token_id")
        side = operation.pop("side")
        price = operation.pop("price", None)
        size = operation.pop("size", None)
        maker_amount = operation.pop("maker_amount", None)
        expiration = operation.pop("expiration", None)
        taker = operation.pop("taker", None)
        post_only = operation.pop("post_only", None)
        market_slug = operation.pop("market_slug")

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
                raise ValueError(
                    f"{order_type.value} orders require price and size"
                )
            unsigned_order = builder.build_order(
                token_id=token_id,
                price=price,
                size=size,
                side=side,
                expiration=expiration,
                taker=taker,
            )

        replacement = CancelReplaceOrderRequest(
            order=CancelReplaceOrderSubmission(**unsigned_order.model_dump()),
            owner_id=on_behalf_of,
            order_type=order_type.value,
            market_slug=market_slug,
            post_only=post_only if order_type == OrderType.GTC else None,
            client_order_id=replacement_client_order_id,
            **operation,
        )
        return CancelReplaceRequest(
            cancel=CancelReplaceTarget(
                order_id=order_id, client_order_id=client_order_id
            ),
            replacement=replacement,
            mode=mode,
            on_behalf_of=on_behalf_of,
        )

    async def cancel_replace(
        self, with_raw_response: bool = False, **operation: Any
    ) -> Union[CancelReplaceResponse, HttpRawResponse]:
        self._http_client.require_auth("cancel_replace_delegated_order")
        request = await self._build_cancel_replace_request(**operation)
        body = request.model_dump(by_alias=True, exclude_none=True, mode="json")
        if with_raw_response:
            return await self._http_client.post_raw(
                "/orders/cancel-replace", body, accepted_statuses={409}
            )
        response = await self._http_client.post(
            "/orders/cancel-replace",
            body,
            accepted_statuses={409},
        )
        return CancelReplaceResponse(**response)

    async def cancel_replace_batch(
        self, operations: List[Dict[str, Any]], with_raw_response: bool = False
    ) -> Union[CancelReplaceBatchResponse, HttpRawResponse]:
        self._http_client.require_auth("cancel_replace_delegated_order")
        requests = [
            await self._build_cancel_replace_request(**dict(operation))
            for operation in operations
        ]
        payload = CancelReplaceBatchRequest(operations=requests)
        body = payload.model_dump(by_alias=True, exclude_none=True, mode="json")
        if with_raw_response:
            return await self._http_client.post_raw("/orders/cancel-replace/batch", body)
        response = await self._http_client.post("/orders/cancel-replace/batch", body)
        return CancelReplaceBatchResponse(**response)

    async def cancel_on_behalf_of(
        self, order_id: str, on_behalf_of: int, with_raw_response: bool = False
    ) -> Union[str, HttpRawResponse]:
        self._http_client.require_auth("cancel_delegated_order")
        if not isinstance(on_behalf_of, int) or on_behalf_of <= 0:
            raise ValueError("on_behalf_of must be a positive integer")

        path = f"/orders/{quote(order_id, safe='')}"
        params = {"onBehalfOf": on_behalf_of}
        if with_raw_response:
            return await self._http_client.delete_raw(path, params=params)
        response = CancelResponse(
            **await self._http_client.delete(path, params=params)
        )
        return response.message

    async def cancel_all(
        self, market_slug: str, with_raw_response: bool = False
    ) -> Union[str, HttpRawResponse]:
        self._http_client.require_auth("cancel_all_delegated_orders")
        path = f"/orders/all/{quote(market_slug, safe='')}"
        if with_raw_response:
            return await self._http_client.delete_raw(path)
        response = CancelResponse(**await self._http_client.delete(path))
        return response.message

    async def cancel_all_on_behalf_of(
        self,
        market_slug: str,
        on_behalf_of: int,
        with_raw_response: bool = False,
    ) -> Union[str, HttpRawResponse]:
        self._http_client.require_auth("cancel_all_delegated_orders")
        if not isinstance(on_behalf_of, int) or on_behalf_of <= 0:
            raise ValueError("on_behalf_of must be a positive integer")

        path = f"/orders/all/{quote(market_slug, safe='')}"
        params = {"onBehalfOf": on_behalf_of}
        if with_raw_response:
            return await self._http_client.delete_raw(path, params=params)
        response = CancelResponse(
            **await self._http_client.delete(path, params=params)
        )
        return response.message
