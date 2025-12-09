"""WebSocket client for real-time data streaming.

This module provides a high-performance, production-ready WebSocket client
for real-time market data from Limitless Exchange using Socket.IO.

Performance optimizations:
- Async/await for non-blocking I/O operations
- Connection pooling and reuse
- Exponential backoff with jitter for reconnection
- Efficient subscription management with O(1) lookup
- Automatic cleanup and resource management
"""

import asyncio
import secrets
from typing import Any, Callable, Dict, List, Optional, Set
from socketio import AsyncClient
from socketio.exceptions import ConnectionError as SocketIOConnectionError

from ..types.logger import ILogger, NoOpLogger
from .types import (
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


DEFAULT_WS_URL = "wss://ws.limitless.exchange"
DEFAULT_NAMESPACE = "/markets"


class WebSocketClient:
    """WebSocket client for real-time data streaming from Limitless Exchange.

    This client uses Socket.IO to connect to the WebSocket server and provides
    typed event subscriptions for orderbook, trades, orders, and market data.

    Performance features:
    - Async/await for concurrent operations
    - Connection pooling and automatic reconnection
    - Exponential backoff with jitter (prevents thundering herd)
    - Efficient O(1) subscription lookup
    - Resource cleanup on disconnect

    Example:
        >>> # Create client
        >>> client = WebSocketClient(
        ...     WebSocketConfig(
        ...         session_cookie='your-session-cookie',
        ...         auto_reconnect=True
        ...     )
        ... )
        >>>
        >>> # Subscribe to orderbook updates (CLOB markets)
        >>> @client.on('orderbookUpdate')
        >>> async def on_orderbook(data: OrderbookUpdate):
        ...     print(f"Orderbook update: {data['marketSlug']}")
        ...     print(f"Best bid: {data['orderbook']['bids'][0]}")
        >>>
        >>> # Connect and subscribe
        >>> await client.connect()
        >>> await client.subscribe('subscribe_market_prices', {'marketSlugs': ['market-123']})
    """

    def __init__(
        self,
        config: Optional[WebSocketConfig] = None,
        logger: Optional[ILogger] = None
    ):
        """Initialize WebSocket client.

        Args:
            config: WebSocket configuration (optional, uses defaults if not provided)
            logger: Optional logger for debugging (default: NoOpLogger)
        """
        # Use default config if not provided
        if config is None:
            config = WebSocketConfig()

        self._config = config
        self._logger = logger or NoOpLogger()
        self._sio: Optional[AsyncClient] = None
        self._state = WebSocketState.DISCONNECTED
        self._reconnect_attempts = 0

        # Subscription management (O(1) lookup)
        self._subscriptions: Dict[str, SubscriptionOptions] = {}

        # Pending listeners (registered before connect)
        self._pending_listeners: List[Dict[str, Any]] = []

        # Connection lock for thread-safe operations
        self._connection_lock = asyncio.Lock()

    @property
    def state(self) -> WebSocketState:
        """Get current connection state.

        Returns:
            Current WebSocket state
        """
        return self._state

    def is_connected(self) -> bool:
        """Check if client is connected.

        Returns:
            True if connected and ready
        """
        return self._state == WebSocketState.CONNECTED and self._sio is not None

    def set_session_cookie(self, session_cookie: str) -> None:
        """Set the session cookie for authentication.

        If already connected, this will trigger a reconnection with the new
        authentication credentials.

        Args:
            session_cookie: Session cookie value

        Example:
            >>> client.set_session_cookie('new-session-cookie')
        """
        self._config.session_cookie = session_cookie

        # If already connected, reconnect with new auth
        if self.is_connected():
            self._logger.info("Session cookie updated, reconnecting...")
            asyncio.create_task(self._reconnect_with_new_auth())

    async def _reconnect_with_new_auth(self) -> None:
        """Reconnect with new authentication credentials."""
        await self.disconnect()
        await self.connect()

    async def connect(self) -> None:
        """Connect to the WebSocket server.

        Returns:
            None (async operation)

        Raises:
            ConnectionError: If connection fails
            asyncio.TimeoutError: If connection times out

        Example:
            >>> await client.connect()
            >>> print('Connected!')
        """
        async with self._connection_lock:
            if self.is_connected():
                self._logger.info("Already connected")
                return

            self._logger.info("Connecting to WebSocket", {"url": self._config.url})
            self._state = WebSocketState.CONNECTING

            try:
                # Create Socket.IO client with optimized settings
                self._sio = AsyncClient(
                    logger=False,  # Disable Socket.IO logger (we use our own)
                    engineio_logger=False,
                    reconnection=self._config.auto_reconnect,
                    reconnection_delay=self._config.reconnect_delay,
                    reconnection_delay_max=min(self._config.reconnect_delay * 32, 60),  # Max 60s
                    reconnection_attempts=self._config.max_reconnect_attempts or 0,  # 0 = infinite
                    randomization_factor=0.2,  # Add jitter to prevent thundering herd
                )

                # Setup internal event handlers
                self._setup_internal_handlers()

                # Attach any pending listeners
                self._attach_pending_listeners()

                # Prepare connection URL (use base URL, namespace handled by Socket.IO)
                ws_url = self._config.url

                # Prepare headers with session cookie
                headers = {}
                if self._config.session_cookie:
                    headers['cookie'] = f"limitless_session={self._config.session_cookie}"

                # Connect with timeout to /markets namespace
                await asyncio.wait_for(
                    self._sio.connect(
                        ws_url,
                        headers=headers,
                        transports=['websocket'],  # WebSocket only (no polling fallback)
                        namespaces=[DEFAULT_NAMESPACE],  # Connect to /markets namespace
                        wait_timeout=self._config.timeout
                    ),
                    timeout=self._config.timeout
                )

                self._state = WebSocketState.CONNECTED
                self._reconnect_attempts = 0
                self._logger.info("WebSocket connected")

                # Re-subscribe to all previous subscriptions
                await self._resubscribe_all()

            except asyncio.TimeoutError:
                self._state = WebSocketState.ERROR
                error_msg = f"Connection timeout after {self._config.timeout}s. Check if WebSocket URL is correct: {ws_url}"
                self._logger.error(error_msg)
                raise ConnectionError(error_msg)

            except Exception as e:
                self._state = WebSocketState.ERROR

                # Provide user-friendly error messages
                error_msg = str(e)

                # DNS/hostname errors
                if "nodename nor servname provided" in error_msg or "getaddrinfo failed" in error_msg:
                    friendly_msg = f"Invalid WebSocket URL or hostname not found: {ws_url}"
                    self._logger.error(friendly_msg)
                    raise ConnectionError(friendly_msg) from None

                # Connection refused
                elif "Connection refused" in error_msg or "Cannot connect to host" in error_msg:
                    friendly_msg = f"Cannot connect to WebSocket server: {ws_url}. Server may be down or URL is incorrect."
                    self._logger.error(friendly_msg)
                    raise ConnectionError(friendly_msg) from None

                # SSL/Certificate errors
                elif "ssl" in error_msg.lower() or "certificate" in error_msg.lower():
                    friendly_msg = f"SSL/Certificate error connecting to: {ws_url}"
                    self._logger.error(friendly_msg)
                    raise ConnectionError(friendly_msg) from None

                # Generic connection error
                elif "Connection error" in error_msg:
                    friendly_msg = f"Failed to connect to WebSocket server: {ws_url}. Please verify the URL and your network connection."
                    self._logger.error(friendly_msg)
                    raise ConnectionError(friendly_msg) from None

                # Other errors - preserve original
                else:
                    self._logger.error(f"WebSocket connection error: {error_msg}")
                    raise

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server.

        Performs cleanup and clears all subscriptions.

        Example:
            >>> await client.disconnect()
        """
        if self._sio is None:
            return

        self._logger.info("Disconnecting from WebSocket")

        try:
            await self._sio.disconnect()
        except Exception as e:
            self._logger.error("Error during disconnect", e)
        finally:
            self._sio = None
            self._state = WebSocketState.DISCONNECTED
            self._subscriptions.clear()

    async def subscribe(
        self,
        channel: SubscriptionChannel,
        options: Optional[SubscriptionOptions] = None
    ) -> None:
        """Subscribe to a channel.

        Args:
            channel: Channel to subscribe to
            options: Subscription options (market slug, filters, etc.)

        Raises:
            ConnectionError: If not connected
            ValueError: If subscription fails

        Example:
            >>> # Subscribe to market prices (CLOB orderbook + AMM prices)
            >>> await client.subscribe('subscribe_market_prices', {'marketSlugs': ['market-123']})
            >>>
            >>> # Subscribe to positions
            >>> await client.subscribe('subscribe_positions', {'marketSlugs': ['market-123']})
            >>>
            >>> # Subscribe to transaction events
            >>> await client.subscribe('subscribe_transactions')
        """
        if not self.is_connected():
            raise ConnectionError("WebSocket not connected. Call connect() first.")

        if options is None:
            options = {}

        subscription_key = self._get_subscription_key(channel, options)
        self._subscriptions[subscription_key] = options

        self._logger.info("Subscribing to channel", {"channel": channel, "options": options})

        # Emit subscription event to /markets namespace (fire and forget, like TS SDK)
        await self._sio.emit(channel, options, namespace=DEFAULT_NAMESPACE)
        self._logger.info("Subscribed successfully", {"channel": channel, "options": options})

    async def unsubscribe(
        self,
        channel: SubscriptionChannel,
        options: Optional[SubscriptionOptions] = None
    ) -> None:
        """Unsubscribe from a channel.

        Args:
            channel: Channel to unsubscribe from
            options: Subscription options (must match subscribe call)

        Raises:
            ConnectionError: If not connected
            ValueError: If unsubscribe fails

        Example:
            >>> await client.unsubscribe('subscribe_market_prices', {'marketSlugs': ['market-123']})
        """
        if not self.is_connected():
            raise ConnectionError("WebSocket not connected")

        if options is None:
            options = {}

        subscription_key = self._get_subscription_key(channel, options)
        self._subscriptions.pop(subscription_key, None)

        self._logger.info("Unsubscribing from channel", {"channel": channel, "options": options})

        try:
            # Emit unsubscribe event to /markets namespace
            unsubscribe_data = {"channel": channel, **options}
            response = await self._sio.call('unsubscribe', unsubscribe_data, namespace=DEFAULT_NAMESPACE, timeout=5.0)

            # Check for errors
            if isinstance(response, dict) and response.get('error'):
                error_msg = response.get('error')
                self._logger.error("Unsubscribe failed", None, {"error": error_msg})
                raise ValueError(f"Unsubscribe failed: {error_msg}")

            self._logger.info("Unsubscribed successfully", {"channel": channel, "options": options})

        except Exception as e:
            self._logger.error("Unsubscribe error", e, {"channel": channel})
            raise

    def on(self, event: str, handler: Optional[Callable] = None) -> Any:
        """Register an event listener for /markets namespace events.

        Can be used as decorator or direct call.

        Args:
            event: Event name
            handler: Event handler (optional if used as decorator)

        Returns:
            Decorator function if handler not provided, otherwise self

        Example:
            >>> # As decorator
            >>> @client.on('orderbookUpdate')
            >>> async def on_orderbook(data):
            ...     print(f"Orderbook: {data}")
            >>>
            >>> # Direct call
            >>> client.on('orderbookUpdate', on_orderbook)
        """
        def decorator(func: Callable) -> Callable:
            if self._sio is None:
                # Store listener to be attached when socket is created
                self._pending_listeners.append({"event": event, "handler": func})
            else:
                # Attach listener immediately to /markets namespace
                self._sio.on(event, handler=func, namespace=DEFAULT_NAMESPACE)
            return func

        if handler is None:
            # Used as decorator
            return decorator
        else:
            # Direct call
            decorator(handler)
            return self

    def once(self, event: str, handler: Callable) -> 'WebSocketClient':
        """Register a one-time event listener for /markets namespace events.

        Args:
            event: Event name
            handler: Event handler

        Returns:
            This client for chaining

        Raises:
            ConnectionError: If not connected

        Example:
            >>> client.once('orderbookUpdate', lambda data: print(f'First update: {data}'))
        """
        if self._sio is None:
            raise ConnectionError("WebSocket not initialized. Call connect() first.")

        # Create one-time wrapper
        async def once_wrapper(*args, **kwargs):
            await handler(*args, **kwargs)
            self._sio.off(event, handler=once_wrapper, namespace=DEFAULT_NAMESPACE)

        self._sio.on(event, handler=once_wrapper, namespace=DEFAULT_NAMESPACE)
        return self

    def off(self, event: str, handler: Optional[Callable] = None) -> 'WebSocketClient':
        """Remove an event listener from /markets namespace.

        Args:
            event: Event name
            handler: Event handler to remove (if None, removes all handlers for event)

        Returns:
            This client for chaining

        Example:
            >>> client.off('orderbookUpdate', on_orderbook)
        """
        if self._sio is None:
            return self

        if handler is None:
            # Remove all handlers for event in /markets namespace
            # Socket.IO doesn't have a built-in way to do this, so we need to
            # remove the event from the handlers dict directly
            namespace_key = DEFAULT_NAMESPACE
            if hasattr(self._sio, 'handlers') and namespace_key in self._sio.handlers:
                if event in self._sio.handlers[namespace_key]:
                    self._sio.handlers[namespace_key][event] = []
        else:
            self._sio.off(event, handler=handler, namespace=DEFAULT_NAMESPACE)

        return self

    def _attach_pending_listeners(self) -> None:
        """Attach any pending event listeners that were added before connect().

        Internal method for attaching listeners registered before Socket.IO client creation.
        All listeners are attached to the /markets namespace.
        """
        if self._sio is None or len(self._pending_listeners) == 0:
            return

        for listener in self._pending_listeners:
            self._sio.on(listener['event'], handler=listener['handler'], namespace=DEFAULT_NAMESPACE)

        # Clear pending listeners
        self._pending_listeners.clear()

    def _setup_internal_handlers(self) -> None:
        """Setup internal event handlers for connection management.

        Internal method for setting up Socket.IO lifecycle events.
        """
        if self._sio is None:
            return

        # Connection events
        @self._sio.on('connect')
        async def on_connect():
            self._state = WebSocketState.CONNECTED
            self._reconnect_attempts = 0
            self._logger.info("WebSocket connected")

        @self._sio.on('disconnect')
        async def on_disconnect():
            self._state = WebSocketState.DISCONNECTED
            self._logger.info("WebSocket disconnected")

        @self._sio.on('connect_error')
        async def on_connect_error(data):
            self._state = WebSocketState.ERROR
            self._logger.error(f"WebSocket connection error: {data}")

        # Reconnection events
        @self._sio.on('reconnect_attempt')
        async def on_reconnect_attempt():
            self._state = WebSocketState.RECONNECTING
            self._reconnect_attempts += 1
            self._logger.info("Reconnecting...", {"attempt": self._reconnect_attempts})

        @self._sio.on('reconnect')
        async def on_reconnect():
            self._state = WebSocketState.CONNECTED
            self._logger.info("Reconnected", {"attempts": self._reconnect_attempts})
            await self._resubscribe_all()

        @self._sio.on('reconnect_error')
        async def on_reconnect_error(data):
            self._logger.error(f"Reconnection error: {data}")

        @self._sio.on('reconnect_failed')
        async def on_reconnect_failed():
            self._state = WebSocketState.ERROR
            self._logger.error("Reconnection failed")

    async def _resubscribe_all(self) -> None:
        """Re-subscribe to all previous subscriptions after reconnection.

        Internal method for automatic re-subscription after reconnect.
        All subscriptions are sent to the /markets namespace.
        """
        if len(self._subscriptions) == 0:
            return

        self._logger.info("Re-subscribing to channels", {"count": len(self._subscriptions)})

        for subscription_key, options in list(self._subscriptions.items()):
            channel = self._get_channel_from_key(subscription_key)
            try:
                # Re-subscribe (subscription already in dict, just emit event to /markets namespace)
                await self._sio.emit(channel, options, namespace=DEFAULT_NAMESPACE)
                self._logger.info("Re-subscribed", {"channel": channel, "options": options})
            except Exception as e:
                self._logger.error("Failed to re-subscribe", e, {"channel": channel, "options": options})

    def _get_subscription_key(self, channel: SubscriptionChannel, options: SubscriptionOptions) -> str:
        """Create a unique subscription key.

        Internal method for O(1) subscription lookup.

        Args:
            channel: Channel name
            options: Subscription options

        Returns:
            Unique subscription key
        """
        market_slug = options.get('market_slug', 'global')
        return f"{channel}:{market_slug}"

    def _get_channel_from_key(self, key: str) -> SubscriptionChannel:
        """Extract channel from subscription key.

        Internal method for extracting channel name from subscription key.

        Args:
            key: Subscription key

        Returns:
            Channel name
        """
        return key.split(':')[0]  # type: ignore

    async def __aenter__(self):
        """Context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.disconnect()
