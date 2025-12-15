"""Order client for managing orders on Limitless Exchange."""

from typing import Optional
from eth_account import Account

from ..api.http_client import HttpClient
from ..types.orders import (
    Side,
    OrderType,
    MarketType,
    SignedOrder,
    CreateOrderDto,
    OrderResponse,
    OrderSigningConfig,
    UnsignedOrder,
)
from ..types.auth import UserData
from ..types.logger import ILogger, NoOpLogger
from ..utils.constants import get_contract_address
from .builder import OrderBuilder
from .signer import OrderSigner


class OrderClient:
    """High-level order management client.

    This class provides methods for creating and managing orders,
    abstracting away HTTP details and order signing complexity.

    Args:
        http_client: HTTP client for API requests
        wallet: Ethereum account for signing
        user_data: User data containing userId and feeRateBps
        market_type: Market type for auto-configuration (default: CLOB)
        signing_config: Custom signing configuration (optional)
        logger: Optional logger for debugging

    Example:
        >>> from eth_account import Account
        >>> from limitless_sdk.api import HttpClient
        >>> from limitless_sdk.orders import OrderClient
        >>> from limitless_sdk.types import UserData, Side, OrderType, MarketType
        >>>
        >>> # Setup
        >>> account = Account.from_key(private_key)
        >>> http_client = HttpClient()
        >>> user_data = UserData(user_id=123, fee_rate_bps=300)
        >>>
        >>> # Create order client
        >>> order_client = OrderClient(
        ...     http_client=http_client,
        ...     wallet=account,
        ...     user_data=user_data,
        ...     market_type=MarketType.CLOB
        ... )
        >>>
        >>> # Create order
        >>> order = await order_client.create_order(
        ...     token_id="123456",
        ...     price=0.65,
        ...     size=100.0,
        ...     side=Side.BUY,
        ...     order_type=OrderType.GTC,
        ...     market_slug="bitcoin-price-2024"
        ... )
    """

    def __init__(
        self,
        http_client: HttpClient,
        wallet: Account,
        user_data: UserData,
        market_type: MarketType = MarketType.CLOB,
        signing_config: Optional[OrderSigningConfig] = None,
        logger: Optional[ILogger] = None,
    ):
        """Initialize order client.

        Args:
            http_client: HTTP client for API requests
            wallet: Ethereum account for signing
            user_data: User data (userId, feeRateBps)
            market_type: Market type (CLOB or NEGRISK)
            signing_config: Custom signing config (optional)
            logger: Optional logger
        """
        self._http_client = http_client
        self._wallet = wallet
        self._owner_id = user_data.user_id
        self._logger = logger or NoOpLogger()

        # Initialize order builder
        self._builder = OrderBuilder(
            maker_address=wallet.address,
            fee_rate_bps=user_data.fee_rate_bps,
            price_tick=0.001,
        )

        # Initialize order signer
        self._signer = OrderSigner(wallet, logger)

        # Configure signing
        if signing_config:
            self._signing_config = signing_config
        else:
            # Auto-configure from market type
            import os

            # Read chain ID from environment or use default
            chain_id = int(os.getenv("CHAIN_ID", "8453"))  # Base mainnet default

            # Read contract address from environment or use SDK default
            if market_type == MarketType.CLOB:
                contract_address = os.getenv("CLOB_CONTRACT_ADDRESS") or get_contract_address("CLOB", chain_id)
            else:
                contract_address = os.getenv("NEGRISK_CONTRACT_ADDRESS") or get_contract_address("NEGRISK", chain_id)

            self._signing_config = OrderSigningConfig(
                chain_id=chain_id,
                contract_address=contract_address,
                market_type=market_type,
            )

            self._logger.info(
                "Auto-configured signing",
                {
                    "chain_id": chain_id,
                    "contract": contract_address,
                    "market_type": market_type.value,
                },
            )

    async def create_order(
        self,
        token_id: str,
        side: Side,
        order_type: OrderType,
        market_slug: str,
        price: Optional[float] = None,
        size: Optional[float] = None,
        maker_amount: Optional[float] = None,
        expiration: Optional[int] = None,
        taker: Optional[str] = None,
    ) -> OrderResponse:
        """Create and submit a new order.

        This method handles the complete order creation flow:
        1. Build unsigned order with proper amount calculations
        2. Sign order with EIP-712
        3. Submit to API

        Args:
            token_id: Token ID for the outcome
            side: Order side (BUY or SELL)
            order_type: Order type (GTC, FOK, etc.)
            market_slug: Market slug identifier
            price: Price per share (0-1 range) - required for GTC orders
            size: Size in USDC - required for GTC orders
            maker_amount: Maker amount - for FOK orders (BUY: USDC to spend, SELL: shares to sell)
            expiration: Optional expiration timestamp
            taker: Optional taker address

        Returns:
            OrderResponse with order details and maker matches

        Raises:
            ValueError: If parameters are invalid or missing for order type
            APIError: If order creation fails

        Example GTC:
            >>> order = await client.create_order(
            ...     token_id="123456",
            ...     side=Side.BUY,
            ...     order_type=OrderType.GTC,
            ...     market_slug="bitcoin-price-2024",
            ...     price=0.65,
            ...     size=100.0
            ... )

        Example FOK (BUY):
            >>> order = await client.create_order(
            ...     token_id="123456",
            ...     side=Side.BUY,
            ...     order_type=OrderType.FOK,
            ...     market_slug="bitcoin-price-2024",
            ...     maker_amount=50.0  # Spend $50 USDC
            ... )

        Example FOK (SELL):
            >>> order = await client.create_order(
            ...     token_id="123456",
            ...     side=Side.SELL,
            ...     order_type=OrderType.FOK,
            ...     market_slug="bitcoin-price-2024",
            ...     maker_amount=18.64  # Sell 18.64 shares
            ... )
        """
        # Validate parameters based on order type
        is_fok = order_type == OrderType.FOK

        if is_fok:
            if maker_amount is None:
                raise ValueError("FOK orders require 'maker_amount' parameter")

            self._logger.info("Creating FOK order", {
                "side": side.name,
                "order_type": order_type.value,
                "market_slug": market_slug,
                "maker_amount": maker_amount,
            })
        else:
            if price is None or size is None:
                raise ValueError("GTC orders require 'price' and 'size' parameters")
            self._logger.info(
                "Creating GTC order",
                {
                    "side": side.name,
                    "order_type": order_type.value,
                    "market_slug": market_slug,
                    "price": price,
                    "size": size,
                },
            )

        if is_fok:
            unsigned_order = self._builder.build_fok_order(
                token_id=token_id,
                side=side,
                maker_amount=maker_amount,
                expiration=expiration,
                taker=taker,
            )
        else:
            unsigned_order = self._builder.build_order(
                token_id=token_id,
                price=price,
                size=size,
                side=side,
                expiration=expiration,
                taker=taker,
            )

        self._logger.debug(
            "Built unsigned order",
            {
                "salt": unsigned_order.salt,
                "maker_amount": unsigned_order.maker_amount,
                "taker_amount": unsigned_order.taker_amount,
            },
        )

        signature = await self._signer.sign_order(unsigned_order, self._signing_config)

        signed_order = SignedOrder(**unsigned_order.model_dump(), signature=signature)

        payload = CreateOrderDto(
            order=signed_order,
            owner_id=self._owner_id,
            order_type=order_type.value,
            market_slug=market_slug,
        )
        payload_dict = payload.model_dump(by_alias=True)
        self._logger.debug("Submitting order to API", {
            "payload": payload_dict,
            "order_type": order_type.value,
            "market_slug": market_slug,
        })

        response_data = await self._http_client.post(
            "/orders", payload_dict
        )

        self._logger.info(
            "Order created successfully", {"order_id": response_data["order"]["id"]}
        )

        return OrderResponse(**response_data)

    async def cancel(self, order_id: str) -> dict:
        """Cancel an order by ID.

        Args:
            order_id: Order ID to cancel

        Returns:
            Dictionary with cancellation message

        Raises:
            APIError: If cancellation fails

        Example:
            >>> result = await client.cancel("order-id-123")
            >>> print(result["message"])  # "Order canceled successfully"
        """
        self._logger.info("Cancelling order", {"order_id": order_id})

        response = await self._http_client.delete(f"/orders/{order_id}")

        self._logger.info(
            "Order cancelled successfully",
            {"order_id": order_id, "message": response.get("message")},
        )

        return response

    async def cancel_all(self, market_slug: str) -> dict:
        """Cancel all orders for a specific market.

        Args:
            market_slug: Market slug to cancel all orders for

        Returns:
            Dictionary with cancellation message

        Raises:
            APIError: If cancellation fails

        Example:
            >>> result = await client.cancel_all("bitcoin-price-2024")
            >>> print(result["message"])  # "Orders canceled successfully"
        """
        self._logger.info("Cancelling all orders for market", {"market_slug": market_slug})

        response = await self._http_client.delete(f"/orders/all/{market_slug}")

        self._logger.info(
            "All orders cancelled successfully",
            {"market_slug": market_slug, "message": response.get("message")},
        )

        return response

    async def get_order(self, order_id: str) -> OrderResponse:
        """Get order details by ID.

        Args:
            order_id: Order ID to fetch

        Returns:
            OrderResponse with order details

        Raises:
            APIError: If order not found

        Example:
            >>> order = await client.get_order("order-id-123")
            >>> print(f"Side: {order.order.side}")
            >>> print(f"Price: {order.order.price}")
        """
        self._logger.debug("Fetching order", {"order_id": order_id})

        response_data = await self._http_client.get(f"/orders/{order_id}")

        return OrderResponse(**response_data)

    def build_unsigned_order(
        self,
        token_id: str,
        price: float,
        size: float,
        side: Side,
        expiration: Optional[int] = None,
        taker: Optional[str] = None,
    ) -> UnsignedOrder:
        """Build an unsigned order without submitting.

        Useful for advanced use cases where you need the unsigned order
        before signing and submission.

        Args:
            token_id: Token ID for the outcome
            price: Price per share (0-1 range)
            size: Size in USDC
            side: Order side (BUY or SELL)
            expiration: Optional expiration timestamp
            taker: Optional taker address

        Returns:
            UnsignedOrder ready for signing

        Example:
            >>> unsigned = client.build_unsigned_order(
            ...     token_id="123456",
            ...     price=0.65,
            ...     size=100.0,
            ...     side=Side.BUY
            ... )
            >>> print(f"Salt: {unsigned.salt}")
        """
        return self._builder.build_order(
            token_id=token_id,
            price=price,
            size=size,
            side=side,
            expiration=expiration,
            taker=taker,
        )

    async def sign_order(self, order: UnsignedOrder) -> str:
        """Sign an unsigned order without submitting.

        Useful for advanced use cases where you need to inspect
        the signature before submission.

        Args:
            order: Unsigned order to sign

        Returns:
            Signature as hex string

        Example:
            >>> signature = await client.sign_order(unsigned_order)
            >>> print(f"Signature: {signature[:10]}...")
        """
        return await self._signer.sign_order(order, self._signing_config)

    @property
    def wallet_address(self) -> str:
        """Get the wallet address.

        Returns:
            Ethereum address
        """
        return self._wallet.address

    @property
    def owner_id(self) -> int:
        """Get the owner ID.

        Returns:
            Owner ID from user profile
        """
        return self._owner_id
