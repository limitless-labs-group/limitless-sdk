"""API module for HTTP client and error handling."""

from .http_client import HttpClient
from .errors import (
    APIError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
)
from .retry import (
    retry_on_errors,
    RetryConfig,
    RetryableClient,
)

__all__ = [
    "HttpClient",
    "APIError",
    "AuthenticationError",
    "RateLimitError",
    "ValidationError",
    "retry_on_errors",
    "RetryConfig",
    "RetryableClient",
]
