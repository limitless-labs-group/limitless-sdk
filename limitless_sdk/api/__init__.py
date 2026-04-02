"""API module for HTTP client and error handling."""

from .http_client import HttpClient, HttpRawResponse
from .errors import (
    APIError,
    RateLimitError,
    AuthenticationError,
    ValidationError,
    ConflictError,
)
from .retry import (
    retry_on_errors,
    RetryConfig,
    RetryableClient,
)

__all__ = [
    "HttpClient",
    "HttpRawResponse",
    "APIError",
    "RateLimitError",
    "AuthenticationError",
    "ValidationError",
    "ConflictError",
    "retry_on_errors",
    "RetryConfig",
    "RetryableClient",
]
