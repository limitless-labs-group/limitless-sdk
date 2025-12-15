"""Portfolio data fetcher for Limitless Exchange."""

from typing import List, Optional, Dict, Any
from ..api.http_client import HttpClient
from ..types.portfolio import Position, HistoryResponse
from ..types.logger import ILogger, NoOpLogger


class PortfolioFetcher:
    """Portfolio data fetcher for retrieving user positions and history.

    This class provides methods to fetch portfolio positions and transaction
    history for authenticated users.

    Args:
        http_client: HTTP client for API requests
        logger: Optional logger for debugging (default: NoOpLogger)

    Example:
        >>> from limitless_sdk.api import HttpClient
        >>> from limitless_sdk.portfolio import PortfolioFetcher
        >>>
        >>> http_client = HttpClient()
        >>> fetcher = PortfolioFetcher(http_client)
        >>>
        >>> # Get positions
        >>> positions = await fetcher.get_positions()
        >>> for pos in positions:
        ...     print(f"{pos.market_slug}: {pos.balance}")
    """

    def __init__(self, http_client: HttpClient, logger: Optional[ILogger] = None):
        """Initialize portfolio fetcher.

        Args:
            http_client: HTTP client for API requests
            logger: Optional logger for debugging
        """
        self._http_client = http_client
        self._logger = logger or NoOpLogger()

    async def get_positions(self) -> dict:
        """Get all positions for the authenticated user.

        Returns:
            Raw API response dict with 'clob', 'amm', and 'accumulativePoints'

        Raises:
            AuthenticationError: If not authenticated (401)
            APIError: If API request fails

        Example:
            >>> response = await fetcher.get_positions()
            >>> print(f"CLOB positions: {len(response['clob'])}")
            >>> print(f"AMM positions: {len(response['amm'])}")
            >>> print(f"Points: {response['accumulativePoints']}")
        """
        self._logger.debug("Fetching positions")

        try:
            response_data = await self._http_client.get("/portfolio/positions")
            self._logger.info("Positions fetched successfully")
            return response_data  # Return raw API response 1:1

        except Exception as error:
            self._logger.error("Failed to fetch positions", error)
            raise

    async def get_user_history(self, page: int = 1, limit: int = 10) -> dict:
        """Get paginated history of user actions.

        Includes AMM trades, CLOB trades, splits/merges, and NegRisk conversions.

        Args:
            page: Page number (required, starts at 1)
            limit: Number of items per page (required)

        Returns:
            Raw API response dict with 'data' and 'totalCount'

        Raises:
            AuthenticationError: If not authenticated (401)
            ValidationError: If invalid pagination parameters (400)
            APIError: If API request fails

        Example:
            >>> # Get first page
            >>> response = await fetcher.get_user_history(page=1, limit=20)
            >>> print(f"Found {len(response['data'])} of {response['totalCount']} entries")
            >>>
            >>> # Process history entries
            >>> for entry in response['data']:
            ...     print(f"Type: {entry['type']}")
            ...     print(f"Market: {entry['marketSlug']}")
            >>>
            >>> # Get next page
            >>> page2 = await fetcher.get_user_history(page=2, limit=20)
        """
        self._logger.debug("Fetching user history", {"page": page, "limit": limit})

        try:
            params = {"page": page, "limit": limit}
            response_data = await self._http_client.get("/portfolio/history", params=params)

            self._logger.info("User history fetched successfully")
            return response_data  # Return raw API response 1:1

        except Exception as error:
            self._logger.error("Failed to fetch user history", error, {"page": page, "limit": limit})
            raise
