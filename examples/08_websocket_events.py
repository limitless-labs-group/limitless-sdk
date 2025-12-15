"""
WebSocket Events Example

Subscribe to real-time orderbook updates via WebSocket.

Setup:
    export MARKET_SLUG="your-market-slug"
"""

import asyncio
import os
from dotenv import load_dotenv
from limitless_sdk.websocket import WebSocketClient, WebSocketConfig, OrderbookUpdate

# Load environment variables
load_dotenv()

# Configuration
WS_URL = os.getenv("WS_URL", "wss://ws.limitless.exchange")
MARKET_SLUG = os.getenv("MARKET_SLUG") or "your-market-slug-here"


async def main():
    print(f"Connecting to: {WS_URL}")
    print(f"Market: {MARKET_SLUG}\n")

    # Setup WebSocket
    config = WebSocketConfig(
        url=WS_URL,
        auto_reconnect=True,
        reconnect_delay=1.0,
    )
    ws_client = WebSocketClient(config=config)

    try:
        # Event handlers
        @ws_client.on('connect')
        async def on_connect():
            print(" Connected")

        @ws_client.on('disconnect')
        async def on_disconnect(reason: str):
            print(f" Disconnected: {reason}")

        @ws_client.on('orderbookUpdate')
        async def on_orderbook_update(data: OrderbookUpdate):
            orderbook = data.get('orderbook', data)

            if orderbook.get('bids') and orderbook.get('asks'):
                best_bid = orderbook['bids'][0]['price']
                best_ask = orderbook['asks'][0]['price']
                spread = best_ask - best_bid

                print(f"Bid: {best_bid:.4f} | Ask: {best_ask:.4f} | Spread: {spread:.4f}")

        # Connect and subscribe
        await ws_client.connect()
        await ws_client.subscribe('subscribe_market_prices', {'marketSlugs': [MARKET_SLUG]})

        print(f" Subscribed to {MARKET_SLUG}")
        print("Monitoring updates... (Ctrl+C to stop)\n")

        # Keep running
        await asyncio.Event().wait()

    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nStopping...")
    finally:
        await ws_client.disconnect()
        print("Disconnected")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Already handled in main()
