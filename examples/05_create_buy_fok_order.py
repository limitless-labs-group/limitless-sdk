"""
Create BUY FOK Order Example

Demonstrates creating a FOK (Fill-Or-Kill) BUY order.
FOK orders either fill immediately or are cancelled - no partial fills.

Setup:
    export PRIVATE_KEY="0x..."
    export MARKET_SLUG="your-market-slug"

Note:
    FOK orders use maker_amount instead of price/size
    Amount = total USDC to spend (e.g., 10.0 = $10 USDC)
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

        # Place FOK BUY order
        order = await order_client.create_order(
            token_id=token_id,
            maker_amount=10.0,   # $10 USDC total spend
            side=Side.BUY,
            order_type=OrderType.FOK,
            market_slug=market.slug,
        )

        print(f"\nFOK Order: {order.order.id}")

        # Check if filled
        if order.maker_matches and len(order.maker_matches) > 0:
            print(f" FILLED: {len(order.maker_matches)} matches")
            for match in order.maker_matches:
                print(f"  - Size: {match.matched_size}")
        else:
            print(" NOT FILLED (cancelled - no liquidity)")

    finally:
        await http_client.close()


if __name__ == "__main__":
    asyncio.run(main())
