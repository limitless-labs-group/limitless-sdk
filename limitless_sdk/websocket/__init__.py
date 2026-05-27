"""WebSocket module for real-time data streaming.

This module provides a high-performance WebSocket client for real-time market data
from Limitless Exchange using Socket.IO protocol.

Example:
    >>> from limitless_sdk.websocket import WebSocketClient, WebSocketConfig
    >>> from limitless_sdk.websocket.types import OrderbookUpdate
    >>>
    >>> # Create client
    >>> client = WebSocketClient(
    ...     WebSocketConfig(
    ...         api_key='your-api-key',
    ...         auto_reconnect=True
    ...     )
    ... )
    >>>
    >>> # Subscribe to events
    >>> @client.on('orderbookUpdate')
    >>> async def on_orderbook(data: OrderbookUpdate):
    ...     print(f"Orderbook: {data['marketSlug']}")
    >>>
    >>> # Connect and subscribe
    >>> await client.connect()
    >>> await client.subscribe('subscribe_market_prices', {'marketSlugs': ['market-123']})
"""

from .client import WebSocketClient, DEFAULT_WS_URL
from .types import (
    # State and config
    WebSocketState,
    WebSocketConfig,
    SubscriptionChannel,
    SubscriptionOptions,
    # Event types
    OrderbookEntry,
    OrderbookData,
    OrderbookUpdate,
    AmmPriceEntry,
    NewPriceData,
    OraclePriceData,
    OmeOrderEvent,
    SettlementMakerMatch,
    SettlementOrderEvent,
    OrderEvent,
    LiveSportsMatchData,
    LiveSportsUpdate,
    LiveEsportsMatchScore,
    LiveEsportsMatchData,
    LiveEsportsUpdate,
    SystemEvent,
    TransactionEvent,
    MarketCreatedEvent,
    MarketResolvedEvent,
    WebSocketEvents,
    # Handler types
    ConnectHandler,
    DisconnectHandler,
    ErrorHandler,
    ReconnectingHandler,
    OrderbookHandler,
    NewPriceDataHandler,
    OraclePriceDataHandler,
    TransactionHandler,
    MarketCreatedHandler,
    MarketResolvedHandler,
    OrderEventHandler,
    LiveSportsUpdateHandler,
    LiveEsportsUpdateHandler,
    SystemHandler,
)

__all__ = [
    # Client
    "WebSocketClient",
    "DEFAULT_WS_URL",
    # State and config
    "WebSocketState",
    "WebSocketConfig",
    "SubscriptionChannel",
    "SubscriptionOptions",
    # Event types
    "OrderbookEntry",
    "OrderbookData",
    "OrderbookUpdate",
    "AmmPriceEntry",
    "NewPriceData",
    "OraclePriceData",
    "OmeOrderEvent",
    "SettlementMakerMatch",
    "SettlementOrderEvent",
    "OrderEvent",
    "LiveSportsMatchData",
    "LiveSportsUpdate",
    "LiveEsportsMatchScore",
    "LiveEsportsMatchData",
    "LiveEsportsUpdate",
    "SystemEvent",
    "TransactionEvent",
    "MarketCreatedEvent",
    "MarketResolvedEvent",
    "WebSocketEvents",
    # Handler types
    "ConnectHandler",
    "DisconnectHandler",
    "ErrorHandler",
    "ReconnectingHandler",
    "OrderbookHandler",
    "NewPriceDataHandler",
    "OraclePriceDataHandler",
    "TransactionHandler",
    "MarketCreatedHandler",
    "MarketResolvedHandler",
    "OrderEventHandler",
    "LiveSportsUpdateHandler",
    "LiveEsportsUpdateHandler",
    "SystemHandler",
]
