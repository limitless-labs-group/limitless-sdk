"""Delegated order example using HMAC-scoped partner auth."""

import asyncio
import os

from limitless_sdk import (
    CreatePartnerAccountInput,
    OrderType,
    ScopeAccountCreation,
    ScopeDelegatedSigning,
    ScopeTrading,
    Side,
)

from common import derive_scoped_client, ready_delay_ms, require_env, truthy_env


async def main() -> None:
    identity_token = require_env("LIMITLESS_IDENTITY_TOKEN")
    market_slug = require_env("MARKET_SLUG")
    bootstrap, scoped, derived = await derive_scoped_client(
        identity_token,
        [ScopeTrading, ScopeDelegatedSigning, ScopeAccountCreation],
        label="python-sdk-delegated-order-example",
    )

    try:
        market = await scoped.markets.get_market(market_slug)
        token_id = str(market.tokens.yes)

        account = await scoped.partner_accounts.create_account(
            CreatePartnerAccountInput(
                display_name=os.getenv("PARTNER_ACCOUNT_DISPLAY_NAME", "Python SDK Bot"),
                create_server_wallet=True,
            )
        )

        print("Delegated order setup")
        print(
            f"  market={market.slug} token_id={token_id} "
            f"exchange={market.venue.exchange if market.venue else 'n/a'}"
        )
        print(
            f"  child_profile_id={account.profile_id} child_account={account.account}"
        )
        print(
            f"  derived_token_id={derived.token_id} scopes={derived.scopes}"
        )
        print(f"Fund {account.account} with USDC before placing delegated orders.")

        delay_ms = ready_delay_ms()
        if delay_ms > 0:
            print(f"Waiting {delay_ms}ms for allowance provisioning...")
            await asyncio.sleep(delay_ms / 1000)

        if not truthy_env("LIMITLESS_PLACE_DELEGATED_ORDER"):
            print(
                "Skipping delegated trade. Set LIMITLESS_PLACE_DELEGATED_ORDER=1 after funding the child account."
            )
            return

        response = await scoped.delegated_orders.create_order(
            token_id=token_id,
            side=Side.BUY,
            order_type=OrderType.GTC,
            market_slug=market_slug,
            on_behalf_of=account.profile_id,
            price=float(os.getenv("LIMITLESS_DELEGATED_ORDER_PRICE", "0.05")),
            size=float(os.getenv("LIMITLESS_DELEGATED_ORDER_SIZE", "1")),
        )
        print(f"Created delegated order: {response.order.id}")

        cancel_message = await scoped.delegated_orders.cancel_on_behalf_of(
            response.order.id,
            account.profile_id,
        )
        print(f"Cancelled delegated order by id: {cancel_message}")

        cancel_all_message = await scoped.delegated_orders.cancel_all_on_behalf_of(
            market_slug,
            account.profile_id,
        )
        print(f"Cancelled remaining delegated orders for market: {cancel_all_message}")

    finally:
        await bootstrap.close()
        await scoped.close()


if __name__ == "__main__":
    asyncio.run(main())
