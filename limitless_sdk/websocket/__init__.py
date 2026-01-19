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
    >>> @client.on('orderbook')
    >>> async def on_orderbook(data: OrderbookUpdate):
    ...     print(f"Orderbook: {data['market_slug']}")
    >>>
    >>> # Connect and subscribe
    >>> await client.connect()
    >>> await client.subscribe('orderbook', {'market_slug': 'market-123'})
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
    TradeEvent,
    OrderUpdate,
    FillEvent,
    MarketUpdate,
    PriceUpdate,
    AmmPriceEntry,
    NewPriceData,
    TransactionEvent,
    WebSocketEvents,
    # Handler types
    ConnectHandler,
    DisconnectHandler,
    ErrorHandler,
    ReconnectingHandler,
    OrderbookHandler,
    TradeHandler,
    OrderHandler,
    FillHandler,
    MarketHandler,
    PriceHandler,
    NewPriceDataHandler,
    TransactionHandler,
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
    "TradeEvent",
    "OrderUpdate",
    "FillEvent",
    "MarketUpdate",
    "PriceUpdate",
    "AmmPriceEntry",
    "NewPriceData",
    "TransactionEvent",
    "WebSocketEvents",
    # Handler types
    "ConnectHandler",
    "DisconnectHandler",
    "ErrorHandler",
    "ReconnectingHandler",
    "OrderbookHandler",
    "TradeHandler",
    "OrderHandler",
    "FillHandler",
    "MarketHandler",
    "PriceHandler",
    "NewPriceDataHandler",
    "TransactionHandler",
]
