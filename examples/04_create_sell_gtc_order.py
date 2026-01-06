"""
Create GTC Order Example

Demonstrates creating a GTC (Good-Till-Cancelled) order on a specific market.

Setup:
    export PRIVATE_KEY="0x..."
    export MARKET_SLUG="your-market-slug"
"""

import asyncio
import os
from dotenv import load_dotenv
from eth_account import Account
from limitless_sdk.api import HttpClient
from limitless_sdk.auth import MessageSigner, Authenticator
from limitless_sdk.orders import OrderClient
from limitless_sdk.markets import MarketFetcher
from limitless_sdk.types import (
    LoginOptions,
    Side,
    OrderType,
    UserData,
)

# Load environment variables
load_dotenv()

# Configuration
API_URL = os.getenv("API_URL", "https://api.limitless.exchange")
MARKET_SLUG = os.getenv("MARKET_SLUG") or "your-market-slug-here"


async def main():
    # Setup
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        raise ValueError("Set PRIVATE_KEY in .env file")

    account = Account.from_key(private_key)
    print(f"Wallet: {account.address}")

    http_client = HttpClient(base_url=API_URL)

    try:
        # Authenticate
        signer = MessageSigner(account)
        authenticator = Authenticator(http_client, signer)
        auth_result = await authenticator.authenticate(LoginOptions(client="eoa"))

        user_data = UserData(
            user_id=auth_result.profile.id,
            fee_rate_bps=auth_result.profile.fee_rate_bps
        )

        # Get market by slug
        market_fetcher = MarketFetcher(http_client)
        market = await market_fetcher.get_market(MARKET_SLUG)

        print(f"Market: {market.title}")

        # Get YES token ID
        if not market.tokens or not market.tokens.yes:
            raise ValueError("Market has no YES token")

        token_id = str(market.tokens.yes)

        # Create order client
        order_client = OrderClient(
            http_client=http_client,
            wallet=account,
            user_data=user_data,
        )

        # Place GTC order
        order = await order_client.create_order(
            token_id=token_id,
            price=0.50,      # min price that will execute, can be executed with better one 
            size=5.0,        # amount of shares you wanna SELL, please make sure you have enough to cover sell
            side=Side.SELL,
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
