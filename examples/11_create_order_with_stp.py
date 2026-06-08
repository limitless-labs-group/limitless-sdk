"""
Create Order with Self-Trade Prevention (STP) Example

Demonstrates passing a self-trade-prevention policy on a GTC order and reading
the execution outcome from the response.

STP decides what happens when your incoming order would match your own resting
order:
    - cancel_maker: cancel your resting (maker) order, let the taker proceed (default)
    - cancel_taker: reject the incoming (taker) order, keep your resting order
    - cancel_both: cancel both sides

stp_policy is a top-level request field. It is never part of the signed order, so
it does not affect the EIP-712 signature. When omitted, the venue defaults to
cancel_maker.

The response carries an execution object with the settlement state, fees, raw
totals, and STP signals (reason, stp_maker_cancels).

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
            price=0.45,
            size=5.0,
            side=Side.BUY,
            order_type=OrderType.GTC,
            market_slug=market.slug,
            stp_policy="cancel_maker",  # reject? "cancel_taker" | both? "cancel_both"
        )

        print(f"\nOrder: {order.order.id}")
        print(f"Status: {order.order.status}")

        execution = order.execution
        if execution:
            print(f"Matched: {execution.matched}")
            print(f"Settlement status: {execution.settlement_status}")
            print(f"Effective fee (bps): {execution.effective_fee_bps}")
            print(f"Net USD: {execution.totals_raw.usd_net}")

            if execution.stp_maker_cancels:
                print(f"STP cancelled maker orders: {execution.stp_maker_cancels}")
            if execution.reason:
                print(f"Reason: {execution.reason}")

    finally:
        await http_client.close()


if __name__ == "__main__":
    asyncio.run(main())
