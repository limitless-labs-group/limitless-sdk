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

    async def get_profile(self, address: str) -> dict:
        """Get user profile for a specific wallet address.

        Returns user profile data including user ID and fee rate.

        Args:
            address: Wallet address to fetch profile for

        Returns:
            Raw API response dict with 'id', 'account', 'rank', etc.

        Raises:
            AuthenticationError: If not authenticated (401)
            APIError: If API request fails

        Example:
            >>> response = await fetcher.get_profile('0x1234...')
            >>> print(f"User ID: {response['id']}")
            >>> print(f"Account: {response['account']}")
            >>> print(f"Fee Rate: {response['rank']['feeRateBps']}")
        """
        self._logger.debug("Fetching user profile", {"address": address})

        try:
            response_data = await self._http_client.get(f"/profiles/{address}")
            self._logger.info("User profile fetched successfully", {"address": address})
            return response_data  # Return raw API response 1:1

        except Exception as error:
            self._logger.error("Failed to fetch user profile", error, {"address": address})
            raise

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

    async def get_clob_positions(self) -> list:
        """Get CLOB positions only.

        Returns:
            List of CLOB position dictionaries

        Raises:
            AuthenticationError: If not authenticated (401)
            APIError: If API request fails

        Example:
            >>> clob_positions = await fetcher.get_clob_positions()
            >>> for pos in clob_positions:
            ...     print(f"{pos['market']['title']}: {pos['positions']['yes']['unrealizedPnl']} P&L")
        """
        response = await self.get_positions()
        return response.get('clob', [])

    async def get_amm_positions(self) -> list:
        """Get AMM positions only.

        Returns:
            List of AMM position dictionaries

        Raises:
            AuthenticationError: If not authenticated (401)
            APIError: If API request fails

        Example:
            >>> amm_positions = await fetcher.get_amm_positions()
            >>> for pos in amm_positions:
            ...     print(f"{pos['market']['title']}: {pos['unrealizedPnl']} P&L")
        """
        response = await self.get_positions()
        return response.get('amm', [])

    async def get_user_history(self, cursor: str | None = None, limit: int = 20) -> dict:
        """Get user history with cursor-based pagination.

        Includes AMM trades, CLOB trades, Negrisk trades & conversions.

        Args:
            cursor: Opaque cursor for pagination. Pass None for first page.
                    Use the returned 'nextCursor' value for subsequent pages.
            limit: Number of items per page (1-100, default 20)

        Returns:
            Raw API response dict with 'data' and 'nextCursor'

        Raises:
            AuthenticationError: If not authenticated (401)
            ValidationError: If invalid pagination parameters (400)
            APIError: If API request fails

        Example:
            >>> # Get first page
            >>> response = await fetcher.get_user_history(limit=20)
            >>> print(f"Found {len(response['data'])} entries")
            >>>
            >>> # Process history entries
            >>> for entry in response['data']:
            ...     print(f"Strategy: {entry['strategy']}")
            ...     print(f"Market: {entry.get('market', {}).get('slug')}")
            >>>
            >>> # Get next page using cursor
            >>> if response.get('nextCursor'):
            ...     page2 = await fetcher.get_user_history(cursor=response['nextCursor'])
        """
        self._logger.debug("Fetching user history", {"cursor": cursor, "limit": limit})

        try:
            # Always send cursor= (empty on first page) to use cursor flow;
            # omitting it falls back to the legacy page/limit path.
            params = {"cursor": cursor or "", "limit": limit}
            response_data = await self._http_client.get("/portfolio/history", params=params)

            self._logger.info("User history fetched successfully")
            return response_data  # Return raw API response 1:1

        except Exception as error:
            self._logger.error("Failed to fetch user history", error, {"cursor": cursor, "limit": limit})
            raise
