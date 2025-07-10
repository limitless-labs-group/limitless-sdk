"""Exception classes for Limitless Exchange SDK."""


class LimitlessAPIError(Exception):
    """Base exception for API errors."""
    
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


class RateLimitError(LimitlessAPIError):
    """Exception for rate limiting errors."""
    
    def __init__(self, message: str, status_code: int = 429):
        super().__init__(message, status_code)


class AuthenticationError(LimitlessAPIError):
    """Exception for authentication errors."""
    
    def __init__(self, message: str = "Authentication failed", status_code: int = 401):
        super().__init__(message, status_code)


class ValidationError(LimitlessAPIError):
    """Exception for validation errors."""
    
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message, status_code) 