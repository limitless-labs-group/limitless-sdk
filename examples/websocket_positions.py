"""Example: Subscribe to user positions via WebSocket

This example shows how to subscribe to real-time position updates
for your account using API key authentication.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from limitless_sdk.websocket import WebSocketClient
from limitless_sdk.websocket.types import WebSocketConfig


async def main():
    # Load environment variables
    load_dotenv()

    # Validate API key is set
    api_key = os.getenv('LIMITLESS_API_KEY')
    if not api_key:
        print('❌ Error: LIMITLESS_API_KEY environment variable is not set')
        print('Please set it in your .env file or generate one at:')
        print('https://limitless.exchange')
        sys.exit(1)

    # Create WebSocket client with API key
    client = WebSocketClient(
        WebSocketConfig(
            url=os.getenv('WS_URL', 'wss://ws.limitless.exchange'),
            api_key=api_key,  # Required for positions
            auto_reconnect=True,
        )
    )

    # Setup event handlers
    @client.on('connect')
    async def on_connect():
        print('✅ Connected to WebSocket')

    @client.on('disconnect')
    async def on_disconnect(reason: str):
        print(f'⚠️  Disconnected: {reason}')

    @client.on('error')
    async def on_error(error: Exception):
        print(f'❌ Error: {error}')

    # Listen to position updates
    @client.on('positions')
    async def on_positions(data):
        print('\n📊 Position Update:')
        print(data)

        # Process position data
        if isinstance(data, list):
            for position in data:
                market = position.get('marketSlug') or position.get('marketAddress')
                yes_pos = position.get('yesPosition', 0)
                no_pos = position.get('noPosition', 0)
                value = position.get('value', 0)

                print(f'\nMarket: {market}')
                print(f'  YES Position: {yes_pos}')
                print(f'  NO Position: {no_pos}')
                print(f'  Value: {value}')

    # Listen to system messages
    @client.on('system')
    async def on_system(data):
        print(f"ℹ️  System: {data.get('message', data)}")

    try:
        # Connect to WebSocket
        await client.connect()
        print('Connected to WebSocket with API key authentication\n')

        # Subscribe to positions for specific markets
        market_slugs = os.getenv('MARKET_SLUGS', 'bitcoin-2024').split(',')
        await client.subscribe('subscribe_positions', {
            'marketSlugs': market_slugs
        })

        print(f"Subscribed to positions for markets: {', '.join(market_slugs)}")
        print('Monitoring positions...\n')

        # Keep the client running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print('\nShutting down...')
        await client.disconnect()
    except Exception as e:
        print(f'Fatal error: {e}')
        await client.disconnect()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
