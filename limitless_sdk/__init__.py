"""Limitless Exchange Python SDK.

A modular Python SDK for interacting with the Limitless Exchange platform,
providing type-safe access to CLOB and NegRisk prediction markets.

Example:
    >>> from limitless_sdk.api import HttpClient
    >>> from limitless_sdk.markets import MarketFetcher
    >>>
    >>> http_client = HttpClient()
    >>> market_fetcher = MarketFetcher(http_client)
    >>> markets = await market_fetcher.get_markets()
"""

__version__ = "0.3.0"

# API layer - HTTP client and error handling
from .api import (
    HttpClient,
    APIError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
    retry_on_errors,
    RetryConfig,
    RetryableClient,
)

# Authentication module
from .auth import (
    MessageSigner,
    Authenticator,
    AuthenticatedClient,
)

# Markets module
from .markets import MarketFetcher

# Portfolio module
from .portfolio import PortfolioFetcher

# Orders module
from .orders import (
    OrderBuilder,
    OrderSigner,
    OrderClient,
)

# WebSocket module
from .websocket import (
    WebSocketClient,
    DEFAULT_WS_URL,
    WebSocketState,
    WebSocketConfig,
    SubscriptionChannel,
    SubscriptionOptions,
    OrderbookUpdate,
    TradeEvent,
    OrderUpdate,
    FillEvent,
    MarketUpdate,
    PriceUpdate,
)

# Type definitions
from .types import (
    # Logger types
    ILogger,
    NoOpLogger,
    ConsoleLogger,
    LogLevel,
    # Auth types
    LoginOptions,
    UserProfile,
    AuthResult,
    UserData,
    # Market types
    OrderbookEntry,
    OrderBook,
    MarketPrice,
    MarketOutcome,
    Market,
    MarketsResponse,
    ActiveMarketsSortBy,
    ActiveMarketsParams,
    ActiveMarketsResponse,
    # Order types
    Side,
    OrderType,
    SignatureType,
    MarketType,
    UnsignedOrder,
    SignedOrder,
    CreateOrderDto,
    CancelOrderDto,
    DeleteOrderBatchDto,
    MarketSlugValidator,
    OrderSigningConfig,
    OrderArgs,
    MakerMatch,
    OrderResponse,
    # Portfolio types
    Position,
    HistoryEntry,
    HistoryResponse,
    PortfolioResponse,
)

# Utilities
from .utils import (
    DEFAULT_API_URL,
    DEFAULT_WS_URL,
    NETWORK_CONFIG,
    PROTOCOL_NAME,
    PROTOCOL_VERSION,
    get_contract_address,
)

# Legacy client - maintained for backward compatibility
from .client import LimitlessClient
from .models import (
    Order,
    CreateOrderDto as LegacyCreateOrderDto,
    CancelOrderDto as LegacyCancelOrderDto,
    DeleteOrderBatchDto as LegacyDeleteOrderBatchDto,
    MarketSlugValidator as LegacyMarketSlugValidator,
    OrderType as LegacyOrderType,
    OrderSide,
)
from .exceptions import (
    LimitlessAPIError,
    RateLimitError as LegacyRateLimitError,
    AuthenticationError as LegacyAuthenticationError,
)

__all__ = [
    # Version
    "__version__",
    # API layer
    "HttpClient",
    "APIError",
    "AuthenticationError",
    "RateLimitError",
    "ValidationError",
    "retry_on_errors",
    "RetryConfig",
    "RetryableClient",
    # Auth module
    "MessageSigner",
    "Authenticator",
    "AuthenticatedClient",
    # Markets module
    "MarketFetcher",
    # Portfolio module
    "PortfolioFetcher",
    # Orders module
    "OrderBuilder",
    "OrderSigner",
    "OrderClient",
    # WebSocket module
    "WebSocketClient",
    "DEFAULT_WS_URL",
    "WebSocketState",
    "WebSocketConfig",
    "SubscriptionChannel",
    "SubscriptionOptions",
    "OrderbookUpdate",
    "TradeEvent",
    "OrderUpdate",
    "FillEvent",
    "MarketUpdate",
    "PriceUpdate",
    # Logger types
    "ILogger",
    "NoOpLogger",
    "ConsoleLogger",
    "LogLevel",
    # Auth types
    "LoginOptions",
    "UserProfile",
    "AuthResult",
    "UserData",
    # Market types
    "OrderbookEntry",
    "OrderBook",
    "MarketPrice",
    "MarketOutcome",
    "Market",
    "MarketsResponse",
    "ActiveMarketsSortBy",
    "ActiveMarketsParams",
    "ActiveMarketsResponse",
    # Order types
    "Side",
    "OrderType",
    "SignatureType",
    "MarketType",
    "UnsignedOrder",
    "SignedOrder",
    "CreateOrderDto",
    "CancelOrderDto",
    "DeleteOrderBatchDto",
    "MarketSlugValidator",
    "OrderSigningConfig",
    "OrderArgs",
    "MakerMatch",
    "OrderResponse",
    # Portfolio types
    "Position",
    "HistoryEntry",
    "HistoryResponse",
    "PortfolioResponse",
    # Utils
    "DEFAULT_API_URL",
    "DEFAULT_WS_URL",
    "NETWORK_CONFIG",
    "PROTOCOL_NAME",
    "PROTOCOL_VERSION",
    "get_contract_address",
    # Legacy (backward compatibility)
    "LimitlessClient",
    "Order",
    "LegacyCreateOrderDto",
    "LegacyCancelOrderDto",
    "LegacyDeleteOrderBatchDto",
    "LegacyMarketSlugValidator",
    "LegacyOrderType",
    "OrderSide",
    "LimitlessAPIError",
    "LegacyRateLimitError",
    "LegacyAuthenticationError",
]
