"""
Create BUY FAK Order Example

Demonstrates creating a FAK (Fill-And-Kill) BUY order.
FAK orders use price + size like GTC, but any unmatched remainder is cancelled.

Setup:
    export LIMITLESS_API_KEY="your-api-key"
    export PRIVATE_KEY="0x..."
    export MARKET_SLUG="your-market-slug"

Note:
    FAK orders use price and size
    post_only is not supported for FAK orders
"""

import asyncio
import os

from dotenv import load_dotenv
from eth_account import Account

from limitless_sdk.api import HttpClient
from limitless_sdk.markets import MarketFetcher
from limitless_sdk.orders import OrderClient
from limitless_sdk.types import OrderType, Side

load_dotenv()

API_URL = os.getenv("API_URL", "https://api.limitless.exchange")
LIMITLESS_API_KEY = os.getenv("LIMITLESS_API_KEY")
MARKET_SLUG = os.getenv("MARKET_SLUG") or "your-market-slug-here"


async def main():
    if not LIMITLESS_API_KEY:
        raise ValueError(
            "Set LIMITLESS_API_KEY in .env file\n"
            "Get your API key from: https://limitless.exchange"
        )

    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        raise ValueError("Set PRIVATE_KEY in .env file")

    account = Account.from_key(private_key)
    print(f"Wallet: {account.address}")

    http_client = HttpClient(base_url=API_URL, api_key=LIMITLESS_API_KEY)

    try:
        market_fetcher = MarketFetcher(http_client)
        market = await market_fetcher.get_market(MARKET_SLUG)

        print(f"Market: {market.title}")

        if not market.tokens or not market.tokens.yes:
            raise ValueError("Market has no YES token")

        token_id = str(market.tokens.yes)

        order_client = OrderClient(
            http_client=http_client,
            wallet=account,
        )

        order = await order_client.create_order(
            token_id=token_id,
            price=0.45,      # Maximum price willing to pay
            size=5.0,        # Shares to buy
            side=Side.BUY,
            order_type=OrderType.FAK,
            market_slug=market.slug,
        )

        print(f"\nFAK Order: {order.order.id}")
        print(f"Price: {order.order.price}")
        print(f"Status: {order.order.status}")

        if order.maker_matches:
            print(f"Immediate matches: {len(order.maker_matches)}")
        else:
            print("No immediate match. Unfilled remainder was cancelled.")

    finally:
        await http_client.close()


if __name__ == "__main__":
    asyncio.run(main())
