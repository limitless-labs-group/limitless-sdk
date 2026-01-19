"""WebSocket types for real-time data streaming.

This module provides type definitions for WebSocket connections, events,
and subscriptions for real-time market data from Limitless Exchange.
"""

import os
from enum import Enum
from typing import Any, Callable, Dict, List, Literal, Optional, TypedDict, Union
from pydantic import BaseModel, Field


class WebSocketState(str, Enum):
    """WebSocket connection state.

    Attributes:
        DISCONNECTED: Not connected to server
        CONNECTING: Connection in progress
        CONNECTED: Successfully connected
        RECONNECTING: Attempting to reconnect after disconnect
        ERROR: Connection error occurred
    """
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


# Subscription channel types
SubscriptionChannel = Literal[
    "orderbook",
    "trades",
    "orders",
    "fills",
    "markets",
    "prices",
    "subscribe_market_prices",
    "subscribe_positions",
    "subscribe_transactions"
]


class WebSocketConfig(BaseModel):
    """WebSocket connection configuration.

    Args:
        url: WebSocket URL (default: wss://ws.limitless.exchange)
        api_key: API key for authenticated subscriptions (positions, transactions).
                Not required for public subscriptions (market prices, orderbook).
                You can generate an API key at https://limitless.exchange
                and set LIMITLESS_API_KEY environment variable.
        auto_reconnect: Auto-reconnect on connection loss (default: True)
        reconnect_delay: Reconnection delay in seconds (default: 1.0)
        max_reconnect_attempts: Maximum reconnection attempts (default: None = infinite)
        timeout: Connection timeout in seconds (default: 10.0)
        logger: Optional logger instance

    Example:
        >>> # Public subscription (no API key needed)
        >>> config = WebSocketConfig(
        ...     url="wss://ws.limitless.exchange",
        ...     auto_reconnect=True
        ... )
        >>>
        >>> # Authenticated subscription (API key required)
        >>> import os
        >>> config = WebSocketConfig(
        ...     url="wss://ws.limitless.exchange",
        ...     api_key=os.getenv('LIMITLESS_API_KEY'),
        ...     auto_reconnect=True
        ... )
    """
    url: str = Field(default="wss://ws.limitless.exchange")
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv('LIMITLESS_API_KEY'))
    auto_reconnect: bool = Field(default=True)
    reconnect_delay: float = Field(default=1.0)
    max_reconnect_attempts: Optional[int] = Field(default=None)
    timeout: float = Field(default=10.0)
    logger: Optional[Any] = Field(default=None)


class SubscriptionOptions(TypedDict, total=False):
    """Subscription options for WebSocket channels.

    Attributes:
        marketSlug: Market slug to subscribe to (deprecated - use marketSlugs)
        marketSlugs: Market slugs to subscribe to (array format - required by server)
        marketAddress: Market address to subscribe to (deprecated - use marketAddresses)
        marketAddresses: Market addresses to subscribe to (array format - required by server)
        filters: Additional filters for subscription
    """
    marketSlug: Optional[str]  # Deprecated - use marketSlugs
    marketSlugs: Optional[List[str]]
    marketAddress: Optional[str]  # Deprecated - use marketAddresses
    marketAddresses: Optional[List[str]]
    filters: Optional[Dict[str, Any]]


class OrderbookEntry(TypedDict):
    """Single orderbook entry (bid or ask).

    Attributes:
        price: Price per share (0-1 range)
        size: Size in shares
    """
    price: float
    size: float


class OrderbookData(TypedDict):
    """Orderbook data structure (nested object in OrderbookUpdate).

    Attributes:
        bids: List of bid orders sorted by price descending
        asks: List of ask orders sorted by price ascending
        tokenId: Token ID for the orderbook
        adjustedMidpoint: Adjusted midpoint price
        maxSpread: Maximum spread allowed
        minSize: Minimum order size
    """
    bids: List[OrderbookEntry]
    asks: List[OrderbookEntry]
    tokenId: str
    adjustedMidpoint: float
    maxSpread: float
    minSize: float


class OrderbookUpdate(TypedDict):
    """Orderbook update event - matches API format exactly.

    Attributes:
        marketSlug: Market slug identifier (camelCase to match API)
        orderbook: Nested orderbook data object
        timestamp: Timestamp as Date string or number
    """
    marketSlug: str
    orderbook: OrderbookData
    timestamp: Union[str, int, Any]  # API sends Date, can be string or number after serialization


class TradeEvent(TypedDict):
    """Trade event.

    Attributes:
        marketSlug: Market slug identifier (camelCase to match API)
        side: Trade side (BUY or SELL)
        price: Trade price per share
        size: Trade size in shares
        timestamp: Unix timestamp in milliseconds
        tradeId: Unique trade identifier (camelCase to match API)
    """
    marketSlug: str
    side: Literal["BUY", "SELL"]
    price: float
    size: float
    timestamp: int
    tradeId: str


class OrderUpdate(TypedDict):
    """Order update event.

    Attributes:
        orderId: Order identifier (camelCase to match API)
        marketSlug: Market slug identifier (camelCase to match API)
        side: Order side (BUY or SELL)
        price: Order price (optional for FOK orders)
        size: Order size in shares
        filled: Filled amount in shares
        status: Order status
        timestamp: Unix timestamp in milliseconds
    """
    orderId: str
    marketSlug: str
    side: Literal["BUY", "SELL"]
    price: Optional[float]
    size: float
    filled: float
    status: Literal["OPEN", "FILLED", "CANCELLED", "PARTIALLY_FILLED"]
    timestamp: int


class FillEvent(TypedDict):
    """Order fill event.

    Attributes:
        orderId: Order identifier (camelCase to match API)
        marketSlug: Market slug identifier (camelCase to match API)
        side: Order side (BUY or SELL)
        price: Fill price per share
        size: Fill size in shares
        timestamp: Unix timestamp in milliseconds
        fillId: Unique fill identifier (camelCase to match API)
    """
    orderId: str
    marketSlug: str
    side: Literal["BUY", "SELL"]
    price: float
    size: float
    timestamp: int
    fillId: str


class MarketUpdate(TypedDict):
    """Market update event.

    Attributes:
        marketSlug: Market slug identifier (camelCase to match API)
        lastPrice: Last trade price (optional, camelCase to match API)
        volume24h: 24h volume (optional, camelCase to match API)
        priceChange24h: 24h price change percentage (optional, camelCase to match API)
        timestamp: Unix timestamp in milliseconds
    """
    marketSlug: str
    lastPrice: Optional[float]
    volume24h: Optional[float]
    priceChange24h: Optional[float]
    timestamp: int


class PriceUpdate(TypedDict):
    """Price update event (deprecated - use NewPriceData for AMM prices).

    Note: This type does not match the actual API response.
    Use NewPriceData for the correct AMM price update format.

    Attributes:
        marketSlug: Market slug identifier (camelCase to match API)
        price: Current price
        timestamp: Unix timestamp in milliseconds
    """
    marketSlug: str
    price: float
    timestamp: int


class AmmPriceEntry(TypedDict):
    """Single AMM price entry in updatedPrices array.

    Attributes:
        marketId: Market ID
        marketAddress: Market contract address
        yesPrice: YES token price (0-1 range)
        noPrice: NO token price (0-1 range)
    """
    marketId: int
    marketAddress: str
    yesPrice: float
    noPrice: float


class NewPriceData(TypedDict):
    """AMM price update event (newPriceData) - matches API format exactly.

    Attributes:
        marketAddress: Market contract address (camelCase to match API)
        updatedPrices: Array of price updates for this market
        blockNumber: Blockchain block number
        timestamp: Timestamp as Date string or number
    """
    marketAddress: str
    updatedPrices: List[AmmPriceEntry]
    blockNumber: int
    timestamp: Union[str, int, Any]  # API sends Date, can be string or number after serialization


class TransactionEvent(TypedDict, total=False):
    """Transaction event (blockchain transaction status).

    Attributes:
        userId: User ID (optional)
        txHash: Transaction hash (optional)
        status: Transaction status (CONFIRMED or FAILED)
        source: Transaction source
        timestamp: Transaction timestamp
        marketAddress: Market address (optional)
        marketSlug: Market slug identifier (optional)
        tokenId: Token ID (optional)
        conditionId: Condition ID (optional)
        amountContracts: Amount of contracts (optional, in string format)
        amountCollateral: Amount of collateral (optional, in string format)
        price: Price (optional, in string format)
        side: Trade side (optional, BUY or SELL)
    """
    userId: Optional[int]
    txHash: Optional[str]
    status: Literal["CONFIRMED", "FAILED"]
    source: str
    timestamp: str
    marketAddress: Optional[str]
    marketSlug: Optional[str]
    tokenId: Optional[str]
    conditionId: Optional[str]
    amountContracts: Optional[str]
    amountCollateral: Optional[str]
    price: Optional[str]
    side: Optional[Literal["BUY", "SELL"]]


# Event handler type definitions
ConnectHandler = Callable[[], None]
DisconnectHandler = Callable[[str], None]
ErrorHandler = Callable[[Exception], None]
ReconnectingHandler = Callable[[int], None]
OrderbookHandler = Callable[[OrderbookUpdate], None]
TradeHandler = Callable[[TradeEvent], None]
OrderHandler = Callable[[OrderUpdate], None]
FillHandler = Callable[[FillEvent], None]
MarketHandler = Callable[[MarketUpdate], None]
PriceHandler = Callable[[PriceUpdate], None]
NewPriceDataHandler = Callable[[NewPriceData], None]
TransactionHandler = Callable[[TransactionEvent], None]


class WebSocketEvents(TypedDict, total=False):
    """WebSocket event types with typed handlers.

    Use this for type checking event handler registrations.

    Example:
        >>> def on_orderbook(data: OrderbookUpdate) -> None:
        ...     print(f"Orderbook update: {data['marketSlug']}")
        >>>
        >>> events: WebSocketEvents = {
        ...     'orderbookUpdate': on_orderbook
        ... }
    """
    connect: ConnectHandler
    disconnect: DisconnectHandler
    error: ErrorHandler
    reconnecting: ReconnectingHandler
    orderbookUpdate: OrderbookHandler  # API event name is orderbookUpdate (camelCase)
    newPriceData: NewPriceDataHandler  # API event name is newPriceData (camelCase)
    trade: TradeHandler
    order: OrderHandler
    fill: FillHandler
    market: MarketHandler
    price: PriceHandler  # Deprecated - use newPriceData
    positions: Any  # Position update handler
    tx: TransactionHandler
