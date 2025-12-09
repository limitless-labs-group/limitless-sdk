"""Retry decorator for handling transient failures."""

import asyncio
import time
from functools import wraps
from typing import Callable, List, Optional, Set, TypeVar, Any

from .errors import APIError
from ..types.logger import ILogger, NoOpLogger


T = TypeVar("T")


class RetryConfig:
    """Configuration for retry behavior.

    Args:
        status_codes: HTTP status codes to retry on (default: [429, 500, 502, 503, 504])
        max_retries: Maximum number of retry attempts (default: 3)
        delays: List of delays in seconds for each retry attempt (default: [1, 2, 5])
        exponential_base: Base for exponential backoff if delays not specified (default: 2)
        max_delay: Maximum delay between retries in seconds (default: 60)
        on_retry: Optional callback function called before each retry attempt

    Example:
        >>> config = RetryConfig(
        ...     status_codes=[429, 500],
        ...     max_retries=3,
        ...     delays=[2, 5, 10]
        ... )
    """

    def __init__(
        self,
        status_codes: Optional[Set[int]] = None,
        max_retries: int = 3,
        delays: Optional[List[float]] = None,
        exponential_base: float = 2,
        max_delay: float = 60,
        on_retry: Optional[Callable[[int, Exception, float], None]] = None,
    ):
        """Initialize retry configuration."""
        self.status_codes = status_codes or {429, 500, 502, 503, 504}
        self.max_retries = max_retries
        self.delays = delays
        self.exponential_base = exponential_base
        self.max_delay = max_delay
        self.on_retry = on_retry

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given retry attempt with jitter.

        Uses exponential backoff with jitter to prevent thundering herd problem.
        Jitter adds randomness (±20%) to spread out retry attempts from multiple clients.

        Args:
            attempt: Retry attempt number (0-based)

        Returns:
            Delay in seconds with jitter applied

        Example:
            >>> config = RetryConfig(exponential_base=2)
            >>> # Without jitter: 1s, 2s, 4s
            >>> # With jitter: 0.8-1.2s, 1.6-2.4s, 3.2-4.8s
        """
        import random

        if self.delays:
            # Use specified delays
            base_delay = self.delays[min(attempt, len(self.delays) - 1)]
        else:
            # Exponential backoff
            base_delay = min(self.exponential_base**attempt, self.max_delay)

        # Add jitter (±20%) to prevent thundering herd
        jitter = base_delay * 0.2 * (2 * random.random() - 1)
        return max(0.1, base_delay + jitter)


def retry_on_errors(
    status_codes: Optional[Set[int]] = None,
    max_retries: int = 3,
    delays: Optional[List[float]] = None,
    exponential_base: float = 2,
    max_delay: float = 60,
    logger: Optional[ILogger] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
):
    """Decorator to retry async functions on specific HTTP errors.

    This decorator automatically retries failed API calls based on HTTP status codes.
    Useful for handling transient errors like rate limits (429) or server errors (500, 502, 503).

    Args:
        status_codes: Set of HTTP status codes to retry on (default: {429, 500, 502, 503, 504})
        max_retries: Maximum number of retry attempts (default: 3)
        delays: List of delays in seconds for each retry (default: exponential backoff)
        exponential_base: Base for exponential backoff calculation (default: 2)
        max_delay: Maximum delay between retries in seconds (default: 60)
        logger: Optional logger for retry information
        on_retry: Optional callback called before each retry: fn(attempt, error, delay)

    Returns:
        Decorated async function with retry logic

    Example:
        >>> @retry_on_errors(
        ...     status_codes={429, 500},
        ...     max_retries=3,
        ...     delays=[2, 5, 10]
        ... )
        ... async def create_order(...):
        ...     return await order_client.create_order(...)

        >>> # With callback
        >>> def on_retry_callback(attempt, error, delay):
        ...     print(f"Retry {attempt + 1}: {error}, waiting {delay}s")
        ...
        >>> @retry_on_errors(on_retry=on_retry_callback)
        ... async def fetch_markets():
        ...     return await market_fetcher.get_markets()
    """
    config = RetryConfig(
        status_codes=status_codes,
        max_retries=max_retries,
        delays=delays,
        exponential_base=exponential_base,
        max_delay=max_delay,
        on_retry=on_retry,
    )

    _logger = logger or NoOpLogger()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            # First attempt
            try:
                return await func(*args, **kwargs)
            except APIError as e:
                # Check if we should retry this error
                if e.status_code not in config.status_codes:
                    # Not a retryable error, raise immediately
                    raise
                last_exception = e
                _logger.warn(
                    f"API error in {func.__name__}",
                    {
                        "status_code": e.status_code,
                        "message": e.message,
                        "starting_retries": True,
                    },
                )
            except Exception as e:
                # Non-APIError, don't retry
                raise

            # Retry attempts
            for attempt in range(config.max_retries):
                try:
                    # Calculate delay
                    delay = config.get_delay(attempt)

                    # Call user callback if provided
                    if config.on_retry:
                        config.on_retry(attempt, last_exception, delay)

                    _logger.info(
                        f"Retrying {func.__name__}",
                        {
                            "attempt": attempt + 1,
                            "max_retries": config.max_retries,
                            "delay": delay,
                            "last_error": str(last_exception),
                        },
                    )

                    # Wait before retry
                    await asyncio.sleep(delay)

                    # Retry the function
                    return await func(*args, **kwargs)

                except APIError as e:
                    # Check if we should retry this error
                    if e.status_code not in config.status_codes:
                        # Not a retryable error, raise immediately
                        raise
                    last_exception = e
                    _logger.warn(
                        f"Retry failed for {func.__name__}",
                        {
                            "attempt": attempt + 1,
                            "status_code": e.status_code,
                            "message": e.message,
                        },
                    )
                except Exception as e:
                    # Non-APIError, don't retry
                    raise

            # All retries exhausted
            _logger.error(
                f"All retries exhausted for {func.__name__}",
                last_exception,
                {"max_retries": config.max_retries},
            )
            raise last_exception

        return wrapper

    return decorator


class RetryableClient:
    """Wrapper that adds retry logic to HttpClient methods.

    This class wraps an HttpClient and automatically retries failed requests
    based on configured retry settings.

    Args:
        http_client: HttpClient instance to wrap
        retry_config: Retry configuration (default: RetryConfig())
        logger: Optional logger

    Example:
        >>> from limitless_sdk.api import HttpClient, RetryableClient, RetryConfig
        >>>
        >>> http_client = HttpClient()
        >>> retry_config = RetryConfig(
        ...     status_codes={429, 500, 503},
        ...     max_retries=3,
        ...     delays=[2, 5, 10]
        ... )
        >>> retryable = RetryableClient(http_client, retry_config)
        >>>
        >>> # Automatically retries on 429, 500, 503
        >>> data = await retryable.get("/markets")
    """

    def __init__(
        self,
        http_client: Any,  # HttpClient type
        retry_config: Optional[RetryConfig] = None,
        logger: Optional[ILogger] = None,
    ):
        """Initialize retryable client wrapper.

        Args:
            http_client: HttpClient instance to wrap
            retry_config: Retry configuration
            logger: Optional logger
        """
        self._client = http_client
        self._config = retry_config or RetryConfig()
        self._logger = logger or NoOpLogger()

    async def get(self, path: str, **kwargs) -> Any:
        """GET request with retry logic.

        Args:
            path: Request path
            **kwargs: Additional arguments passed to HttpClient.get()

        Returns:
            Response data

        Raises:
            APIError: If all retries exhausted
        """

        @retry_on_errors(
            status_codes=self._config.status_codes,
            max_retries=self._config.max_retries,
            delays=self._config.delays,
            exponential_base=self._config.exponential_base,
            max_delay=self._config.max_delay,
            logger=self._logger,
            on_retry=self._config.on_retry,
        )
        async def _get():
            return await self._client.get(path, **kwargs)

        return await _get()

    async def post(self, path: str, data: Optional[Any] = None, **kwargs) -> Any:
        """POST request with retry logic.

        Args:
            path: Request path
            data: Request body data
            **kwargs: Additional arguments passed to HttpClient.post()

        Returns:
            Response data

        Raises:
            APIError: If all retries exhausted
        """

        @retry_on_errors(
            status_codes=self._config.status_codes,
            max_retries=self._config.max_retries,
            delays=self._config.delays,
            exponential_base=self._config.exponential_base,
            max_delay=self._config.max_delay,
            logger=self._logger,
            on_retry=self._config.on_retry,
        )
        async def _post():
            return await self._client.post(path, data, **kwargs)

        return await _post()

    async def delete(self, path: str, **kwargs) -> Any:
        """DELETE request with retry logic.

        Args:
            path: Request path
            **kwargs: Additional arguments passed to HttpClient.delete()

        Returns:
            Response data

        Raises:
            APIError: If all retries exhausted
        """

        @retry_on_errors(
            status_codes=self._config.status_codes,
            max_retries=self._config.max_retries,
            delays=self._config.delays,
            exponential_base=self._config.exponential_base,
            max_delay=self._config.max_delay,
            logger=self._logger,
            on_retry=self._config.on_retry,
        )
        async def _delete():
            return await self._client.delete(path, **kwargs)

        return await _delete()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()

    def __getattr__(self, name: str) -> Any:
        """Forward other attributes to wrapped client."""
        return getattr(self._client, name)
