"""Market data fetcher for Limitless Exchange."""

from typing import List, Optional, Dict
from ..api.http_client import HttpClient
from ..types.markets import (
    Market,
    MarketsResponse,
    OrderBook,
    ActiveMarketsParams,
    ActiveMarketsResponse,
    Venue,
)
from ..types.logger import ILogger, NoOpLogger


class MarketFetcher:
    """Market data fetcher for retrieving market information and orderbooks.

    This class provides methods to fetch market data, orderbooks, and prices
    from the Limitless Exchange API.

    Venue Caching:
        The fetcher automatically caches venue information (exchange and adapter addresses)
        when markets are fetched. This optimizes order creation by avoiding redundant API calls.

    Args:
        http_client: HTTP client for API requests
        logger: Optional logger for debugging (default: NoOpLogger)

    Example:
        >>> from limitless_sdk.api import HttpClient
        >>> from limitless_sdk.markets import MarketFetcher
        >>>
        >>> http_client = HttpClient()
        >>> fetcher = MarketFetcher(http_client)
        >>>
        >>> # Get active markets
        >>> response = await fetcher.get_active_markets()
        >>> print(f"Found {len(response.data)} markets")
        >>>
        >>> # Venue is cached after fetching market
        >>> market = await fetcher.get_market("bitcoin-2024")
        >>> venue = fetcher.get_venue("bitcoin-2024")  # Instant, no API call
    """

    def __init__(self, http_client: HttpClient, logger: Optional[ILogger] = None):
        """Initialize market fetcher.

        Args:
            http_client: HTTP client for API requests
            logger: Optional logger for debugging
        """
        self._http_client = http_client
        self._logger = logger or NoOpLogger()
        self._venue_cache: Dict[str, Venue] = {}  # Cache venues by market slug

    async def get_active_markets(
        self, params: Optional[ActiveMarketsParams] = None
    ) -> ActiveMarketsResponse:
        """Get active markets with query parameters and pagination support.

        Args:
            params: Query parameters for filtering and pagination

        Returns:
            ActiveMarketsResponse with data and total count

        Raises:
            APIError: If API request fails

        Example:
            >>> # Get 8 markets sorted by LP rewards
            >>> response = await fetcher.get_active_markets(
            ...     ActiveMarketsParams(limit=8, sortBy="lp_rewards")
            ... )
            >>> print(f"Found {len(response.data)} of {response.totalMarketsCount}")
            >>>
            >>> # Get page 2
            >>> page2 = await fetcher.get_active_markets(
            ...     ActiveMarketsParams(limit=8, page=2, sortBy="ending_soon")
            ... )
        """
        params = params or ActiveMarketsParams()

        # Build query parameters
        query_params = {}
        if params.limit is not None:
            query_params["limit"] = params.limit
        if params.page is not None:
            query_params["page"] = params.page
        if params.sort_by is not None:
            query_params["sortBy"] = params.sort_by

        self._logger.debug("Fetching active markets", params.model_dump())

        try:
            response_data = await self._http_client.get(
                "/markets/active", params=query_params
            )

            response = ActiveMarketsResponse(**response_data)

            self._logger.info(
                "Active markets fetched successfully",
                {
                    "count": len(response.data),
                    "total": response.total_markets_count,
                    "sortBy": params.sort_by,
                    "page": params.page,
                },
            )

            return response

        except Exception as error:
            self._logger.error("Failed to fetch active markets", error, params.model_dump())
            raise

    async def get_market(self, slug: str) -> Market:
        """Get a single market by slug.

        Automatically caches venue information for efficient order creation.
        After calling this method, use get_venue(slug) to retrieve cached venue.

        The returned Market object has http_client attached, enabling fluent API:
            market.get_user_orders()

        Args:
            slug: Market slug identifier

        Returns:
            Market object with http_client attached for fluent API

        Raises:
            APIError: If API request fails or market not found

        Example:
            >>> market = await fetcher.get_market("bitcoin-price-2024")
            >>> print(f"Market: {market.title}")
            >>> print(f"Description: {market.description}")
            >>>
            >>> # Fluent API - get user orders for this market
            >>> orders = await market.get_user_orders()
            >>> print(f"You have {len(orders)} orders")
            >>>
            >>> # Venue is now cached
            >>> venue = fetcher.get_venue("bitcoin-price-2024")
            >>> print(f"Exchange: {venue.exchange}")
        """
        self._logger.debug("Fetching market", {"slug": slug})

        try:
            response_data = await self._http_client.get(f"/markets/{slug}")
            market = Market(**response_data)

            # Attach http_client for fluent API methods like get_user_orders()
            market._http_client = self._http_client

            # Cache venue if present
            if market.venue:
                self._venue_cache[slug] = market.venue
                self._logger.debug(
                    "Cached venue for market",
                    {"slug": slug, "exchange": market.venue.exchange}
                )

            self._logger.info(
                "Market fetched successfully", {"slug": slug, "title": market.title}
            )

            return market

        except Exception as error:
            self._logger.error("Failed to fetch market", error, {"slug": slug})
            raise

    async def get_orderbook(self, slug: str) -> OrderBook:
        """Get the orderbook for a CLOB market.

        Args:
            slug: Market slug identifier

        Returns:
            OrderBook object with bids and asks

        Raises:
            APIError: If API request fails

        Example:
            >>> orderbook = await fetcher.get_orderbook("bitcoin-price-2024")
            >>> print(f"Bids: {len(orderbook.bids)}")
            >>> print(f"Asks: {len(orderbook.asks)}")
            >>> print(f"Token ID: {orderbook.token_id}")
        """
        self._logger.debug("Fetching orderbook", {"slug": slug})

        try:
            response_data = await self._http_client.get(f"/markets/{slug}/orderbook")
            orderbook = OrderBook(**response_data)

            self._logger.info(
                "Orderbook fetched successfully",
                {
                    "slug": slug,
                    "bids": len(orderbook.bids),
                    "asks": len(orderbook.asks),
                    "tokenId": orderbook.token_id,
                },
            )

            return orderbook

        except Exception as error:
            self._logger.error("Failed to fetch orderbook", error, {"slug": slug})
            raise

    def get_venue(self, slug: str) -> Optional[Venue]:
        """Get cached venue information for a market.

        This method retrieves venue information from the cache. Venue data is
        automatically cached when get_market() is called.

        For best performance, always call get_market() before creating orders
        to ensure venue information is cached and available.

        Args:
            slug: Market slug identifier

        Returns:
            Venue object if cached, None otherwise

        Example:
            >>> # First fetch the market to cache venue
            >>> market = await fetcher.get_market("bitcoin-2024")
            >>>
            >>> # Now retrieve cached venue (no API call)
            >>> venue = fetcher.get_venue("bitcoin-2024")
            >>> if venue:
            ...     print(f"Exchange: {venue.exchange}")
            ...     print(f"Adapter: {venue.adapter}")
        """
        return self._venue_cache.get(slug)

