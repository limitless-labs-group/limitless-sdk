"""
API Key Authentication Example

Demonstrates how to authenticate with Limitless Exchange API using an API key.
Also shows how to add custom HTTP headers, logging, and the fluent API.

Features demonstrated:
    ✅ API key authentication from environment variable
    ✅ Portfolio positions and transaction history
    ✅ Fluent API: market.get_user_orders(http_client)
    ✅ Custom HTTP headers (global and per-request)
    ✅ Debug logging with header visibility

Setup:
    Option 1: Environment variable (recommended)
        export LIMITLESS_API_KEY="sk_live_..."

    Option 2: Direct assignment (not recommended for production)
        api_key = "sk_live_..."

Custom Headers:
    Global headers (applied to ALL requests):
        HttpClient(additional_headers={"X-Custom": "value"})

    Per-request headers (applied to single request):
        http_client.get("/path", headers={"X-Request-ID": "123"})

Logging:
    Enable DEBUG logging to see all request headers:
        logger = ConsoleLogger(level=LogLevel.DEBUG)
        HttpClient(logger=logger)
"""

import asyncio
import os
from dotenv import load_dotenv
from limitless_sdk.api import HttpClient, APIError, AuthenticationError
from limitless_sdk.portfolio import PortfolioFetcher
from limitless_sdk.markets import MarketFetcher
from limitless_sdk.types import ConsoleLogger, LogLevel

# Load environment variables from .env file
load_dotenv()

# Configuration
API_URL = "https://api.limitless.exchange"


async def main():
    """Demonstrate API key authentication with authenticated endpoints."""

    # Create logger to see headers in requests
    # LogLevel.DEBUG - shows all headers (X-API-Key is hidden for security)
    # LogLevel.INFO - shows basic request info
    logger = ConsoleLogger(level=LogLevel.DEBUG)

    # Create HTTP client with API key authentication
    # API key is automatically loaded from LIMITLESS_API_KEY environment variable
    # Optional: You can also pass it explicitly with api_key parameter
    http_client = HttpClient(
        base_url=API_URL,
        # api_key=os.getenv("LIMITLESS_API_KEY"),  # Optional explicit API key
        additional_headers={
            "X-Custom-Header": "my-value",
        },
        logger=logger
    )

    try:
        print("Testing API Key Authentication...\n")

        # Test authenticated endpoint (requires API key)
        # If API key is not set or invalid, this will raise AuthenticationError
        portfolio = PortfolioFetcher(http_client)

        try:
            # Get user's portfolio positions (CLOB + AMM + points)
            positions = await portfolio.get_positions()
            print(f"✓ Authentication successful!")
            print(f"  CLOB positions: {len(positions.get('clob', []))}")
            print(f"  AMM positions: {len(positions.get('amm', []))}")
            print(f"  Accumulative points: {positions.get('accumulativePoints', 0)}\n")

            # Get user's transaction history
            history = await portfolio.get_user_history(page=1, limit=5)
            print(f"✓ User history retrieved:")
            print(f"  Total entries: {history.get('totalCount', 0)}")
            print(f"  Showing: {len(history.get('data', []))} entries\n")

            # Demonstrate fluent API: market.get_user_orders()
            # First, get a market (this caches venue data for order signing)
            market_fetcher = MarketFetcher(http_client, logger=logger)

            # Try to get an active market
            active_markets_response = await market_fetcher.get_active_markets({"limit": 1})
            if active_markets_response.data:
                first_market = active_markets_response.data[0]
                print(f"✓ Testing fluent API with market: {first_market.title}")

                # Fluent API: Get user orders for this market (clean!)
                market_orders = await first_market.get_user_orders()
                print(f"  Your orders in this market: {len(market_orders)}")

                if market_orders:
                    print(f"  First order: {market_orders[0].get('side')} @ {market_orders[0].get('price')}")

        except AuthenticationError as e:
            print("✗ Authentication failed - check your API key")
            print(f"  Error: {e.message}")
            print(f"  Status: {e.status_code}")
            print("\nMake sure LIMITLESS_API_KEY environment variable is set correctly.")

        except APIError as e:
            print(f"✗ API Error: {e.status_code} - {e.message}")

    finally:
        await http_client.close()
        print("\nHTTP client closed")


if __name__ == "__main__":
    asyncio.run(main())
