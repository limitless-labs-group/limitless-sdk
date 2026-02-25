"""Exception classes for Limitless Exchange SDK."""

from typing import Any, Optional


class APIError(Exception):
    """Base exception for API errors with rich context."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Any] = None,
        url: Optional[str] = None,
        method: Optional[str] = None,
    ):
        """Initialize API error with context.

        Args:
            message: Error message
            status_code: HTTP status code
            response_data: Raw response data from API
            url: Request URL that caused the error
            method: HTTP method (GET, POST, etc.)
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        self.url = url
        self.method = method

    def is_auth_error(self) -> bool:
        """Check if this is an authentication error (401 or 403).

        Returns:
            True if status code is 401 or 403
        """
        return self.status_code in (401, 403)

    def __str__(self) -> str:
        """String representation with context."""
        parts = []
        if self.method and self.url:
            parts.append(f"{self.method} {self.url}")
        if self.status_code:
            parts.append(f"HTTP {self.status_code}")
        parts.append(self.message)
        return " | ".join(parts)

    def __repr__(self) -> str:
        """String representation of error."""
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"status={self.status_code}, "
            f"url={self.url})"
        )


class RateLimitError(APIError):
    """Exception for rate limiting errors (429)."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        status_code: int = 429,
        response_data: Optional[Any] = None,
        url: Optional[str] = None,
        method: Optional[str] = None,
    ):
        """Initialize rate limit error.

        Args:
            message: Error message
            status_code: HTTP status code (default 429)
            response_data: Raw response data
            url: Request URL
            method: HTTP method
        """
        super().__init__(message, status_code, response_data, url, method)



class AuthenticationError(APIError):
    """Exception for authentication errors (401, 403)."""

    def __init__(
        self,
        message: str = "Authentication failed",
        status_code: int = 401,
        response_data: Optional[Any] = None,
        url: Optional[str] = None,
        method: Optional[str] = None,
    ):
        """Initialize authentication error.

        Args:
            message: Error message
            status_code: HTTP status code (default 401)
            response_data: Raw response data
            url: Request URL
            method: HTTP method
        """
        super().__init__(message, status_code, response_data, url, method)


class ValidationError(APIError):
    """Exception for validation errors (400)."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        response_data: Optional[Any] = None,
        url: Optional[str] = None,
        method: Optional[str] = None,
    ):
        """Initialize validation error.

        Args:
            message: Error message
            status_code: HTTP status code (default 400)
            response_data: Raw response data
            url: Request URL
            method: HTTP method
        """
        super().__init__(message, status_code, response_data, url, method)
