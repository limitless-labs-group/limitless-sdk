"""Authenticated client with automatic retry on token expiration."""

from typing import Callable, TypeVar, Awaitable, Optional
from ..api.http_client import HttpClient
from ..api.errors import APIError
from .authenticator import Authenticator
from ..types.auth import LoginOptions
from ..types.logger import ILogger, NoOpLogger


T = TypeVar("T")


class AuthenticatedClient:
    """Optional helper for automatic authentication retry on token expiration.

    This is an optional convenience wrapper. Users can choose to handle
    authentication retry manually or use this helper for automatic retry logic.

    Args:
        http_client: HTTP client instance
        authenticator: Authenticator instance
        client: Authentication client type ('eoa')
        logger: Optional logger for debugging
        max_retries: Maximum retry attempts for auth errors (default: 1)

    Example:
        >>> from limitless_sdk.api import HttpClient
        >>> from limitless_sdk.auth import Authenticator, MessageSigner, AuthenticatedClient
        >>> from limitless_sdk.markets import MarketFetcher
        >>> from eth_account import Account
        >>>
        >>> # Setup
        >>> account = Account.from_key(private_key)
        >>> http_client = HttpClient()
        >>> signer = MessageSigner(account)
        >>> authenticator = Authenticator(http_client, signer)
        >>>
        >>> # Create authenticated client with auto-retry
        >>> auth_client = AuthenticatedClient(
        ...     http_client=http_client,
        ...     authenticator=authenticator,
        ...     client="eoa"
        ... )
        >>>
        >>> # Use withRetry for automatic re-authentication
        >>> market_fetcher = MarketFetcher(http_client)
        >>> markets = await auth_client.with_retry(
        ...     lambda: market_fetcher.get_markets()
        ... )
    """

    def __init__(
        self,
        http_client: HttpClient,
        authenticator: Authenticator,
        client: str = "eoa",
        logger: Optional[ILogger] = None,
        max_retries: int = 1,
    ):
        """Initialize authenticated client with auto-retry capability.

        Args:
            http_client: HTTP client instance
            authenticator: Authenticator instance
            client: Authentication client type
            logger: Optional logger
            max_retries: Maximum retry attempts
        """
        self._http_client = http_client
        self._authenticator = authenticator
        self._client = client
        self._logger = logger or NoOpLogger()
        self._max_retries = max_retries

    async def with_retry(self, fn: Callable[[], Awaitable[T]]) -> T:
        """Execute a function with automatic retry on authentication errors.

        This method will automatically re-authenticate if it receives a 401 or 403
        error, then retry the operation.

        Args:
            fn: Async function to execute with auth retry

        Returns:
            Result of the function call

        Raises:
            APIError: If max retries exceeded or non-auth error occurs

        Example:
            >>> # Automatic retry on 401/403
            >>> positions = await auth_client.with_retry(
            ...     lambda: portfolio_fetcher.get_positions()
            ... )
            >>>
            >>> # Works with any async operation
            >>> order = await auth_client.with_retry(
            ...     lambda: order_client.create_order(...)
            ... )
        """
        attempts = 0

        while attempts <= self._max_retries:
            try:
                return await fn()
            except APIError as error:
                # Check if it's an auth error and we have retries left
                if error.is_auth_error() and attempts < self._max_retries:
                    self._logger.info(
                        "Authentication expired, re-authenticating...",
                        {"attempt": attempts + 1, "max_retries": self._max_retries},
                    )

                    # Re-authenticate
                    await self._reauthenticate()

                    # Increment attempts and retry
                    attempts += 1
                    continue

                # Not an auth error or no retries left - raise
                raise

        # Should never reach here, but TypeScript needs this
        raise RuntimeError("Unexpected error: exceeded max retries")

    async def _reauthenticate(self) -> None:
        """Re-authenticate with the API.

        Internal method called by with_retry to refresh authentication.
        """
        self._logger.debug("Re-authenticating with API")

        await self._authenticator.authenticate(
            LoginOptions(client=self._client)
        )

        self._logger.info("Re-authentication successful")
