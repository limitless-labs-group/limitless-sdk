"""
Cancel GTC Order Example

Demonstrates cancelling GTC orders - single order by ID or all orders for a market.

Setup:
    export LIMITLESS_API_KEY="your-api-key"
    export PRIVATE_KEY="0x..."

    Option 1 - Cancel single order:
        Set order_id below (line 38)

    Option 2 - Cancel all orders:
        Set market_slug below (line 39)
        Note: Create multiple GTC orders first to see cancel_all in action
"""

import asyncio
import os
from dotenv import load_dotenv
from eth_account import Account
from limitless_sdk.api import HttpClient
from limitless_sdk.orders import OrderClient

# Load environment variables
load_dotenv()

# Configuration
API_URL = os.getenv("API_URL", "https://api.limitless.exchange")
LIMITLESS_API_KEY = os.getenv("LIMITLESS_API_KEY")

# Set order ID to cancel (copy from create_gtc_order output)
order_id = "05d7a88b-4187-479e-9052-09b96f92c194"  # Replace with your order ID

# Or set market slug to cancel all orders
market_slug = "your-market-slug-here"  # Replace with your market slug


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
    print(f"Wallet: {account.address}\n")

    http_client = HttpClient(base_url=API_URL, api_key=LIMITLESS_API_KEY)

    try:
        # Create order client (user data fetched automatically from profile)
        order_client = OrderClient(
            http_client=http_client,
            wallet=account,
        )

        # Option 1: Cancel single order by ID
        if order_id and order_id != "05d7a88b-4187-479e-9052-09b96f92c194":
            print(f"Cancelling order: {order_id}")
            result = await order_client.cancel(order_id)
            print(f" Cancelled: {result.get('message', 'Order canceled')}\n")

        # Option 2: Cancel all orders for market
        if market_slug and market_slug != "your-market-slug-here":
            print(f"Cancelling all orders for: {market_slug}")
            print("(Create multiple GTC orders first to see this in action)")
            result = await order_client.cancel_all(market_slug)
            print(f" Cancelled all: {result.get('message', 'All orders canceled')}")

        if (order_id == "05d7a88b-4187-479e-9052-09b96f92c194" and
            market_slug == "your-market-slug-here"):
            print("No order_id or market_slug set. Update lines 36-37 with your values.")

    finally:
        await http_client.close()


if __name__ == "__main__":
    asyncio.run(main())
