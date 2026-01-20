"""Order client for managing orders on Limitless Exchange."""

from typing import Optional
from eth_account import Account

from ..api.http_client import HttpClient
from ..types.orders import (
    Side,
    OrderType,
    SignedOrder,
    CreateOrderDto,
    OrderResponse,
    OrderSigningConfig,
    UnsignedOrder,
)
from ..types.user import UserData
from ..types.logger import ILogger, NoOpLogger
from ..utils.constants import ZERO_ADDRESS
from ..markets.fetcher import MarketFetcher
from ..portfolio.fetcher import PortfolioFetcher
from .builder import OrderBuilder
from .signer import OrderSigner


class OrderClient:
    """High-level order management client.

    This class provides methods for creating and managing orders,
    abstracting away HTTP details and order signing complexity.

    User data (userId, feeRateBps) is automatically fetched from the profile API
    on first order creation and cached for subsequent orders.

    Uses dynamic venue addressing for EIP-712 order signing. For best performance,
    provide a shared market_fetcher instance to enable venue caching across market
    fetches and order creation.

    Args:
        http_client: HTTP client for API requests (must have API key configured)
        wallet: Ethereum account for signing
        signing_config: Custom signing configuration (optional)
        market_fetcher: Shared MarketFetcher instance for venue caching (optional)
        logger: Optional logger for debugging

    Example:
        >>> from eth_account import Account
        >>> from limitless_sdk.api import HttpClient
        >>> from limitless_sdk.orders import OrderClient
        >>> from limitless_sdk.markets import MarketFetcher
        >>> from limitless_sdk.types import Side, OrderType
        >>>
        >>> # Setup
        >>> account = Account.from_key(private_key)
        >>> http_client = HttpClient(api_key="your-api-key")
        >>>
        >>> # Best practice: share MarketFetcher for venue caching
        >>> market_fetcher = MarketFetcher(http_client)
        >>>
        >>> # Create order client (user data fetched automatically)
        >>> order_client = OrderClient(
        ...     http_client=http_client,
        ...     wallet=account,
        ...     market_fetcher=market_fetcher
        ... )
        >>>
        >>> # Venue is cached
        >>> market = await market_fetcher.get_market("bitcoin-2024")
        >>>
        >>> # Uses cached venue, no extra API call
        >>> # User data fetched automatically on first order
        >>> order = await order_client.create_order(
        ...     token_id="123456",
        ...     price=0.65,
        ...     size=100.0,
        ...     side=Side.BUY,
        ...     order_type=OrderType.GTC,
        ...     market_slug="bitcoin-2024"
        ... )
    """

    def __init__(
        self,
        http_client: HttpClient,
        wallet: Account,
        signing_config: Optional[OrderSigningConfig] = None,
        market_fetcher: Optional[MarketFetcher] = None,
        logger: Optional[ILogger] = None,
    ):
        """Initialize order client.

        Args:
            http_client: HTTP client for API requests (must have API key configured)
            wallet: Ethereum account for signing
            signing_config: Custom signing config (optional)
            market_fetcher: Shared MarketFetcher for venue caching (optional)
            logger: Optional logger
        """
        self._http_client = http_client
        self._wallet = wallet
        self._logger = logger or NoOpLogger()

        # User data will be lazily loaded on first order creation
        self._cached_user_data: Optional[UserData] = None
        self._builder: Optional[OrderBuilder] = None

        # Initialize order signer
        self._signer = OrderSigner(wallet, logger)

        # Initialize or use provided market fetcher for venue caching
        self._market_fetcher = market_fetcher or MarketFetcher(http_client, logger)

        # Configure signing
        if signing_config:
            self._signing_config = signing_config
        else:
            # Auto-configure base settings
            import os

            # Read chain ID from environment or use default
            chain_id = int(os.getenv("CHAIN_ID", "8453"))  # Base mainnet default

            # Note: contractAddress is a placeholder here and will be dynamically replaced
            # with venue.exchange in create_order(). The actual contract address comes from
            # the venue system (market.venue.exchange).
            contract_address = ZERO_ADDRESS

            self._signing_config = OrderSigningConfig(
                chain_id=chain_id,
                contract_address=contract_address,
            )

            self._logger.info(
                "Auto-configured signing (contract address from venue)",
                {"chain_id": chain_id},
            )

    async def _ensure_user_data(self) -> UserData:
        """Ensure user data is loaded and cached.

        Fetches from profile API on first call, then caches for subsequent calls.

        Returns:
            Cached user data
        """
        if not self._cached_user_data:
            self._logger.info(
                "Fetching user profile for order client initialization...",
                {"wallet_address": self._wallet.address}
            )

            portfolio_fetcher = PortfolioFetcher(self._http_client, self._logger)
            profile = await portfolio_fetcher.get_profile(self._wallet.address)

            self._cached_user_data = UserData(
                user_id=profile["id"],
                fee_rate_bps=profile.get("rank", {}).get("feeRateBps", 300)
            )

            # Initialize order builder with fetched data
            self._builder = OrderBuilder(
                maker_address=self._wallet.address,
                fee_rate_bps=self._cached_user_data.fee_rate_bps,
                price_tick=0.001,
            )

            self._logger.info(
                "Order Client initialized",
                {
                    "wallet_address": profile["account"],
                    "user_id": self._cached_user_data.user_id,
                    "fee_rate": f"{self._cached_user_data.fee_rate_bps / 100}%",
                }
            )

        return self._cached_user_data

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
        1. Resolve venue address (from cache or API)
        2. Build unsigned order with proper amount calculations
        3. Sign order with EIP-712 using venue.exchange as verifyingContract
        4. Submit to API

        Performance best practice: Always call market_fetcher.get_market(market_slug)
        before create_order() to cache venue data and avoid additional API requests.

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
            >>> # Best practice: fetch market first to cache venue
            >>> market = await market_fetcher.get_market("bitcoin-2024")
            >>>
            >>> order = await client.create_order(
            ...     token_id="123456",
            ...     side=Side.BUY,
            ...     order_type=OrderType.GTC,
            ...     market_slug="bitcoin-2024",
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
        # Ensure user data is loaded (lazy loading with cache)
        user_data = await self._ensure_user_data()

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

        # Step 1: Resolve venue from cache or fetch market
        venue = self._market_fetcher.get_venue(market_slug)

        if not venue:
            self._logger.warning(
                f"Venue not cached, fetching market details. "
                f"For better performance, call market_fetcher.get_market() before create_order().",
                {"market_slug": market_slug}
            )

            market = await self._market_fetcher.get_market(market_slug)

            if not market.venue:
                raise ValueError(
                    f"Market {market_slug} does not have venue information. "
                    f"Venue data is required for order signing."
                )

            venue = market.venue

        # Create dynamic signing config with venue.exchange
        dynamic_signing_config = OrderSigningConfig(
            chain_id=self._signing_config.chain_id,
            contract_address=venue.exchange,
        )

        self._logger.debug(
            "Using venue for order signing",
            {
                "market_slug": market_slug,
                "exchange": venue.exchange,
                "adapter": venue.adapter,
            }
        )

        # Step 2: Build unsigned order
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

        # Step 3: Sign order with dynamic venue
        signature = await self._signer.sign_order(unsigned_order, dynamic_signing_config)

        signed_order = SignedOrder(**unsigned_order.model_dump(), signature=signature)

        payload = CreateOrderDto(
            order=signed_order,
            owner_id=user_data.user_id,
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

    async def build_unsigned_order(
        self,
        token_id: str,
        side: Side,
        price: Optional[float] = None,
        size: Optional[float] = None,
        maker_amount: Optional[float] = None,
        expiration: Optional[int] = None,
        taker: Optional[str] = None,
    ) -> UnsignedOrder:
        """Build an unsigned order without submitting.

        Useful for advanced use cases where you need the unsigned order
        before signing and submission.

        Supports both GTC and FOK order types:
        - GTC orders: Provide price and size parameters
        - FOK orders: Provide maker_amount parameter

        Args:
            token_id: Token ID for the outcome
            side: Order side (BUY or SELL)
            price: Price per share (0-1 range) - required for GTC orders
            size: Size in USDC - required for GTC orders
            maker_amount: Maker amount - for FOK orders (BUY: USDC to spend, SELL: shares to sell)
            expiration: Optional expiration timestamp
            taker: Optional taker address

        Returns:
            UnsignedOrder ready for signing

        Raises:
            ValueError: If parameters are invalid or missing for order type

        Example GTC:
            >>> unsigned = await client.build_unsigned_order(
            ...     token_id="123456",
            ...     side=Side.BUY,
            ...     price=0.65,
            ...     size=100.0
            ... )
            >>> print(f"Salt: {unsigned.salt}")

        Example FOK:
            >>> unsigned = await client.build_unsigned_order(
            ...     token_id="123456",
            ...     side=Side.BUY,
            ...     maker_amount=50.0  # Spend $50 USDC
            ... )
            >>> print(f"Maker amount: {unsigned.maker_amount}")
        """
        # Ensure user data is loaded for order builder
        await self._ensure_user_data()

        # Determine order type based on provided parameters
        is_fok = maker_amount is not None

        if is_fok:
            # Build FOK order
            return self._builder.build_fok_order(
                token_id=token_id,
                side=side,
                maker_amount=maker_amount,
                expiration=expiration,
                taker=taker,
            )
        else:
            # Build GTC order
            if price is None or size is None:
                raise ValueError("GTC orders require 'price' and 'size' parameters")

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
    def owner_id(self) -> Optional[int]:
        """Get the owner ID.

        Returns:
            Owner ID from user profile, or None if not yet loaded
        """
        return self._cached_user_data.user_id if self._cached_user_data else None
