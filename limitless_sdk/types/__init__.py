"""Type definitions for Limitless Exchange SDK."""

from .logger import ILogger, NoOpLogger, ConsoleLogger, LogLevel
from .user import UserProfile, UserData
from .markets import (
    OrderbookEntry,
    OrderBook,
    MarketPrice,
    MarketOutcome,
    Market,
    MarketsResponse,
    ActiveMarketsSortBy,
    ActiveMarketsParams,
    ActiveMarketsResponse,
)
from .orders import (
    Side,
    OrderType,
    SignatureType,
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
)
from .portfolio import (
    Position,
    HistoryEntry,
    HistoryResponse,
    PortfolioResponse,
)

__all__ = [
    # Logger types
    "ILogger",
    "NoOpLogger",
    "ConsoleLogger",
    "LogLevel",
    # User types
    "UserProfile",
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
]
