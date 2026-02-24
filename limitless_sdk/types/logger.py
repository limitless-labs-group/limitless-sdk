"""Logger protocol and implementations for SDK."""

import logging
from enum import Enum
from typing import Any, Optional, Protocol


class LogLevel(Enum):
    """Log level enumeration."""

    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class ILogger(Protocol):
    """Logger protocol for dependency injection.

    This protocol defines the logging interface used throughout the SDK.
    Users can provide custom logger implementations.
    """

    def debug(self, message: str, context: Optional[Any] = None) -> None:
        """Log debug message.

        Args:
            message: Debug message
            context: Optional context dict or object
        """
        ...

    def info(self, message: str, context: Optional[Any] = None) -> None:
        """Log info message.

        Args:
            message: Info message
            context: Optional context dict or object
        """
        ...

    def warn(self, message: str, context: Optional[Any] = None) -> None:
        """Log warning message.

        Args:
            message: Warning message
            context: Optional context dict or object
        """
        ...

    def error(
        self, message: str, error: Optional[Exception] = None, context: Optional[Any] = None
    ) -> None:
        """Log error message.

        Args:
            message: Error message
            error: Optional exception object
            context: Optional context dict or object
        """
        ...


class NoOpLogger:
    """No-operation logger (default) - produces no output.

    This is the default logger used throughout the SDK to avoid
    cluttering user output unless they explicitly configure logging.
    """

    def debug(self, message: str, context: Optional[Any] = None) -> None:
        """No-op debug logging."""
        pass

    def info(self, message: str, context: Optional[Any] = None) -> None:
        """No-op info logging."""
        pass

    def warn(self, message: str, context: Optional[Any] = None) -> None:
        """No-op warning logging."""
        pass

    warning = warn

    def error(
        self, message: str, error: Optional[Exception] = None, context: Optional[Any] = None
    ) -> None:
        """No-op error logging."""
        pass


class ConsoleLogger:
    """Console logger for development and debugging.

    Args:
        level: Minimum log level to output (default: INFO)
        name: Logger name (default: "limitless_sdk")

    Example:
        >>> from limitless_sdk.types import ConsoleLogger, LogLevel
        >>> logger = ConsoleLogger(level=LogLevel.DEBUG)
        >>> logger.info("Test message", {"user_id": 123})
    """

    def __init__(self, level: LogLevel = LogLevel.INFO, name: str = "limitless_sdk"):
        """Initialize console logger.

        Args:
            level: Minimum log level to output
            name: Logger name for identification
        """
        self._level = level
        self._logger = logging.getLogger(name)

        # Configure Python logging if not already configured
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
            self._logger.setLevel(self._get_python_level(level))

    def _get_python_level(self, level: LogLevel) -> int:
        """Convert LogLevel to Python logging level."""
        mapping = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARN: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
        }
        return mapping.get(level, logging.INFO)

    def _should_log(self, level: LogLevel) -> bool:
        """Check if message should be logged based on configured level."""
        levels = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARN, LogLevel.ERROR]
        return levels.index(level) >= levels.index(self._level)

    def _format_context(self, context: Optional[Any]) -> str:
        """Format context for logging."""
        if context is None:
            return ""
        if isinstance(context, dict):
            parts = [f"{k}={v}" for k, v in context.items()]
            return f" [{', '.join(parts)}]"
        return f" [{context}]"

    def debug(self, message: str, context: Optional[Any] = None) -> None:
        """Log debug message."""
        if self._should_log(LogLevel.DEBUG):
            self._logger.debug(f"{message}{self._format_context(context)}")

    def info(self, message: str, context: Optional[Any] = None) -> None:
        """Log info message."""
        if self._should_log(LogLevel.INFO):
            self._logger.info(f"{message}{self._format_context(context)}")

    def warn(self, message: str, context: Optional[Any] = None) -> None:
        """Log warning message."""
        if self._should_log(LogLevel.WARN):
            self._logger.warning(f"{message}{self._format_context(context)}")

    warning = warn

    def error(
        self, message: str, error: Optional[Exception] = None, context: Optional[Any] = None
    ) -> None:
        """Log error message."""
        if self._should_log(LogLevel.ERROR):
            error_str = f" - {error}" if error else ""
            self._logger.error(f"{message}{error_str}{self._format_context(context)}")
