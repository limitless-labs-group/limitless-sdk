"""Delegated FOK order example using HMAC-scoped partner auth."""

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
        label="python-sdk-delegated-fok-order-example",
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

        print("Delegated FOK order setup")
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
        print(f"Fund {account.account} with USDC before placing delegated FOK orders.")

        delay_ms = ready_delay_ms()
        if delay_ms > 0:
            print(f"Waiting {delay_ms}ms for allowance provisioning...")
            await asyncio.sleep(delay_ms / 1000)

        if not truthy_env("LIMITLESS_PLACE_DELEGATED_ORDER"):
            print(
                "Skipping delegated FOK trade. Set LIMITLESS_PLACE_DELEGATED_ORDER=1 after funding the child account."
            )
            return

        maker_amount = 1.0
        print(
            f"Submitting delegated FOK BUY order: maker_amount={maker_amount} USDC "
            f"on_behalf_of={account.profile_id}"
        )

        response = await scoped.delegated_orders.create_order(
            token_id=token_id,
            side=Side.BUY,
            order_type=OrderType.FOK,
            market_slug=market_slug,
            on_behalf_of=account.profile_id,
            maker_amount=maker_amount,
        )
        print(f"Created delegated FOK order: {response.order.id}")

        if response.maker_matches:
            print(
                f"Delegated FOK order fully matched with {len(response.maker_matches)} fill(s)."
            )
        else:
            print(
                "Delegated FOK order was not matched and was cancelled automatically."
            )

    finally:
        await bootstrap.close()
        await scoped.close()


if __name__ == "__main__":
    asyncio.run(main())
