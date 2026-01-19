"""
Create GTC Order Example

Demonstrates creating a GTC (Good-Till-Cancelled) order on a specific market.

Setup:
    export LIMITLESS_API_KEY="your-api-key"
    export PRIVATE_KEY="0x..."
    export MARKET_SLUG="your-market-slug"
"""

import asyncio
import os
from dotenv import load_dotenv
from eth_account import Account
from limitless_sdk.api import HttpClient
from limitless_sdk.orders import OrderClient
from limitless_sdk.markets import MarketFetcher
from limitless_sdk.types import Side, OrderType

# Load environment variables
load_dotenv()

# Configuration
API_URL = os.getenv("API_URL", "https://api.limitless.exchange")
LIMITLESS_API_KEY = os.getenv("LIMITLESS_API_KEY")
MARKET_SLUG = os.getenv("MARKET_SLUG") or "your-market-slug-here"


async def main():
    # Validate API key
    if not LIMITLESS_API_KEY:
        raise ValueError(
            "Set LIMITLESS_API_KEY in .env file\n"
            "Get your API key from: https://limitless.exchange"
        )

    # Setup
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        raise ValueError("Set PRIVATE_KEY in .env file")

    account = Account.from_key(private_key)
    print(f"Wallet: {account.address}")

    http_client = HttpClient(base_url=API_URL, api_key=LIMITLESS_API_KEY)

    try:

        # Get market by slug
        market_fetcher = MarketFetcher(http_client)
        market = await market_fetcher.get_market(MARKET_SLUG)

        print(f"Market: {market.title}")

        # Get YES token ID
        if not market.tokens or not market.tokens.yes:
            raise ValueError("Market has no YES token")

        token_id = str(market.tokens.yes)

        # Create order client (user data fetched automatically from profile)
        order_client = OrderClient(
            http_client=http_client,
            wallet=account,
        )

        # Place GTC order
        order = await order_client.create_order(
            token_id=token_id,
            price=0.50,      # Maximum price willing to pay (can execute at lower price)
            size=5.0,        # Amount of shares you want to buy
            side=Side.BUY,
            order_type=OrderType.GTC,
            market_slug=market.slug,
        )

        print(f"\nOrder created: {order.order.id}")
        print(f"Price: {order.order.price}")
        print(f"Status: {order.order.status}")

        if order.maker_matches:
            print(f"Matched: {len(order.maker_matches)} fills")

    finally:
        await http_client.close()


if __name__ == "__main__":
    asyncio.run(main())
