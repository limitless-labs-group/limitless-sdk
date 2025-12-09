"""Market data fetcher for Limitless Exchange."""

from typing import List, Optional
from ..api.http_client import HttpClient
from ..types.markets import (
    Market,
    MarketsResponse,
    OrderBook,
    ActiveMarketsParams,
    ActiveMarketsResponse,
)
from ..types.logger import ILogger, NoOpLogger


class MarketFetcher:
    """Market data fetcher for retrieving market information and orderbooks.

    This class provides methods to fetch market data, orderbooks, and prices
    from the Limitless Exchange API.

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
    """

    def __init__(self, http_client: HttpClient, logger: Optional[ILogger] = None):
        """Initialize market fetcher.

        Args:
            http_client: HTTP client for API requests
            logger: Optional logger for debugging
        """
        self._http_client = http_client
        self._logger = logger or NoOpLogger()

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

        Args:
            slug: Market slug identifier

        Returns:
            Market object

        Raises:
            APIError: If API request fails or market not found

        Example:
            >>> market = await fetcher.get_market("bitcoin-price-2024")
            >>> print(f"Market: {market.title}")
            >>> print(f"Description: {market.description}")
        """
        self._logger.debug("Fetching market", {"slug": slug})

        try:
            response_data = await self._http_client.get(f"/markets/{slug}")
            market = Market(**response_data)

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

