"""WebSocket types for real-time data streaming.

This module provides type definitions for WebSocket connections, events,
and subscriptions for real-time market data from Limitless Exchange.
"""

import os
from enum import Enum
from typing import Any, Callable, Dict, List, Literal, Optional, TypedDict, Union
from pydantic import BaseModel, Field

from ..types.api_tokens import HMACCredentials


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
    "subscribe_market_prices",
    "subscribe_positions",
    "subscribe_transactions",
    "subscribe_order_events",
    "subscribe_live_sports",
    "subscribe_live_esports",
    "subscribe_market_lifecycle",
    "unsubscribe_market_lifecycle",
]


class WebSocketConfig(BaseModel):
    """WebSocket connection configuration.

    Args:
        url: WebSocket URL (default: wss://ws.limitless.exchange)
        api_key: API key for authenticated subscriptions (positions, transactions,
                order lifecycle events). Not required for public market-price subscriptions.
                You can generate an API key at https://limitless.exchange
                and set LIMITLESS_API_KEY environment variable.
        hmac_credentials: Scoped HMAC credentials for authenticated subscriptions.
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
    hmac_credentials: Optional[HMACCredentials] = Field(default=None)
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
        adjustedMidpoint: Adjusted midpoint price (levels below minSize dropped)
        midpoint: Midpoint of the best displayed bid and ask, without the minSize filter
        maxSpread: Maximum spread allowed
        minSize: Minimum order size
    """
    bids: List[OrderbookEntry]
    asks: List[OrderbookEntry]
    tokenId: str
    adjustedMidpoint: float
    midpoint: float
    maxSpread: float
    minSize: float


class OrderbookUpdate(TypedDict):
    """Orderbook update event - matches API format exactly.

    Attributes:
        marketSlug: Market slug identifier (camelCase to match API)
        orderbook: Nested orderbook data object
        version: Publisher sequence for the book. Increases with every frame while the
            same publisher is active and can restart after a backend failover. The initial
            snapshot sent after subscribing carries 0 when it came from the database fallback.
        timestamp: Timestamp as Date string or number
    """
    marketSlug: str
    orderbook: OrderbookData
    version: int
    timestamp: Union[str, int, Any]  # API sends Date, can be string or number after serialization


class AmmPriceEntry(TypedDict):
    """Single AMM price entry in newPriceData.updatedPrices.

    This is not used by orderbookUpdate; CLOB orderbook updates use
    OrderbookData.

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


class OraclePriceData(TypedDict):
    """Oracle price update event.

    Attributes:
        marketAddress: Market contract address when available
        marketSlug: Market slug identifier
        timestamp: Unix timestamp in milliseconds
        value: Oracle price value
    """
    marketAddress: Optional[str]
    marketSlug: str
    timestamp: int
    value: float


class OmeOrderEvent(TypedDict, total=False):
    """OME order lifecycle event.

    Covers OME lifecycle frames (``PLACEMENT``/``UPDATE``/``CANCELLATION``) and
    the FAK/FOK terminal ``EXECUTION`` frame. ``eventId`` is a numeric serial for
    lifecycle frames and the string ``"terminal:<orderId>"`` for ``EXECUTION``.
    ``status`` is present only on ``EXECUTION``.
    """
    clientOrderId: str
    eventId: Union[int, str]
    marketId: str
    orderId: str
    price: float
    remainingSize: float
    side: str
    source: Literal["OME"]
    status: Literal["FILLED", "PARTIALLY_FILLED", "KILLED"]
    timestamp: str
    token: str
    type: Literal["PLACEMENT", "UPDATE", "CANCELLATION", "EXECUTION"]
    userId: int


class SettlementMakerMatch(TypedDict):
    """Maker match included in settlement order events."""
    account: str
    matchedSize: str
    orderId: str
    price: str


class SettlementOrderEvent(TypedDict, total=False):
    """Settlement order lifecycle event.

    Covers the on-chain ``MINED``/``FAILED`` settlement frames and the
    pre-settlement per-fill ``MATCHED`` frame. On ``MATCHED`` the amounts/fees are
    an estimate (``isEstimate`` is True) and the maker side reports a fee of 0
    while the taker reports a real estimate.
    """
    amountCollateral: str
    amountContracts: str
    clientOrderId: str
    configuredFeeRateBps: int
    effectiveFeeBps: int
    eventId: str
    feeAmountCollateral: str
    feeAmountContracts: str
    isEstimate: bool
    makerMatches: List[SettlementMakerMatch]
    marketSlug: str
    orderId: str
    price: str
    side: str
    source: Literal["SETTLEMENT"]
    takerAccount: str
    takerOrderId: str
    timestamp: Union[str, int, Any]
    token: Literal["YES", "NO"]
    tokenId: str
    tradeEventId: str
    txHash: str
    type: Literal["MINED", "FAILED", "MATCHED"]


OrderEvent = Union[OmeOrderEvent, SettlementOrderEvent]


class LiveSportsMatchData(TypedDict):
    """Live sports match data."""
    awayScore: Optional[int]
    elapsedMinutes: Optional[int]
    extraMinutes: Optional[int]
    fixtureId: int
    homeScore: Optional[int]
    isFinished: bool
    statusShort: str


LiveSportsUpdate = Dict[str, LiveSportsMatchData]


class LiveEsportsMatchScore(TypedDict):
    """Live esports match score."""
    away: int
    home: int


class LiveEsportsMatchData(TypedDict, total=False):
    """Live esports match data."""
    gameScores: List[LiveEsportsMatchScore]
    isFinished: bool
    matchId: int
    matchScore: LiveEsportsMatchScore
    status: str


LiveEsportsUpdate = Dict[str, LiveEsportsMatchData]
SystemEvent = Union[str, Dict[str, Any]]


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


class MarketCreatedEvent(TypedDict, total=False):
    """Market-created lifecycle event.

    Attributes:
        slug: Market slug identifier
        title: Human-readable market title
        type: Market venue type
        groupSlug: Group market slug when present
        categoryIds: Category identifiers when present
        createdAt: Market creation timestamp
    """
    slug: str
    title: str
    type: Literal["AMM", "CLOB"]
    groupSlug: Optional[str]
    categoryIds: Optional[List[int]]
    createdAt: Union[str, int, Any]


class MarketResolvedEvent(TypedDict):
    """Market-resolved lifecycle event.

    Attributes:
        slug: Market slug identifier
        type: Market venue type
        winningOutcome: Winning outcome label
        winningIndex: Winning outcome index
        resolutionDate: Market resolution timestamp
    """
    slug: str
    type: Literal["AMM", "CLOB"]
    winningOutcome: Literal["YES", "NO"]
    winningIndex: Literal[0, 1]
    resolutionDate: Union[str, int, Any]


# Event handler type definitions
ConnectHandler = Callable[[], None]
DisconnectHandler = Callable[[str], None]
ErrorHandler = Callable[[Exception], None]
ReconnectingHandler = Callable[[int], None]
OrderbookHandler = Callable[[OrderbookUpdate], None]
NewPriceDataHandler = Callable[[NewPriceData], None]
OraclePriceDataHandler = Callable[[OraclePriceData], None]
TransactionHandler = Callable[[TransactionEvent], None]
MarketCreatedHandler = Callable[[MarketCreatedEvent], None]
MarketResolvedHandler = Callable[[MarketResolvedEvent], None]
OrderEventHandler = Callable[[OrderEvent], None]
LiveSportsUpdateHandler = Callable[[LiveSportsUpdate], None]
LiveEsportsUpdateHandler = Callable[[LiveEsportsUpdate], None]
SystemHandler = Callable[[SystemEvent], None]


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
    oraclePriceData: OraclePriceDataHandler  # API event name is oraclePriceData (camelCase)
    orderEvent: OrderEventHandler
    marketCreated: MarketCreatedHandler
    marketResolved: MarketResolvedHandler
    live_sports_update: LiveSportsUpdateHandler
    live_esports_update: LiveEsportsUpdateHandler
    system: SystemHandler
    positions: Any  # Position update handler
    tx: TransactionHandler
