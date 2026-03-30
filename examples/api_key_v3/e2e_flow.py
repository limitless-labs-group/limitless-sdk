"""Narrated end-to-end partner api-token v3 flow."""

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
        label="python-sdk-e2e-flow",
    )

    try:
        print("1. Read current partner capabilities with the Privy identity token.")
        capabilities = await bootstrap.api_tokens.get_capabilities(identity_token)
        print(
            f"   Capabilities: enabled={capabilities.token_management_enabled} "
            f"allowed_scopes={capabilities.allowed_scopes}"
        )

        print("2. Derive a scoped HMAC token for partner operations.")
        print(
            f"   Derived token: token_id={derived.token_id} "
            f"profile_id={derived.profile.id} scopes={derived.scopes}"
        )

        print("3. Verify the derived HMAC token works on authenticated partner endpoints.")
        tokens = await scoped.api_tokens.list_tokens()
        print(f"   Active tokens visible to scoped client: {len(tokens)}")

        print("4. Fetch the market that will be used for delegated trading.")
        market = await scoped.markets.get_market(market_slug)
        print(
            f"   Market: slug={market.slug} "
            f"exchange={market.venue.exchange if market.venue else 'n/a'} "
            f"collateral={market.collateral_token.symbol if market.collateral_token else 'n/a'}"
        )

        print("5. Create a partner-owned child account with a server wallet.")
        account = await scoped.partner_accounts.create_account(
            CreatePartnerAccountInput(
                display_name=os.getenv("PARTNER_ACCOUNT_DISPLAY_NAME", "Python SDK Bot"),
                create_server_wallet=True,
            )
        )
        print(
            f"   Created partner account: profile_id={account.profile_id} account={account.account}"
        )

        print("6. Important: fund the created account before attempting to trade.")
        if market.collateral_token:
            print(
                f"   Fund {account.account} with {market.collateral_token.symbol} "
                f"on {market.collateral_token.address}."
            )
        print(
            "   New server wallets also need the backend allowance provisioning "
            "to finish before the first delegated trade."
        )

        delay_ms = ready_delay_ms()
        if delay_ms > 0:
            print(f"   Waiting {delay_ms}ms before the delegated trade step...")
            await asyncio.sleep(delay_ms / 1000)

        if not truthy_env("LIMITLESS_PLACE_DELEGATED_ORDER"):
            print("7. Trading step skipped.")
            print(
                "   Re-run with LIMITLESS_PLACE_DELEGATED_ORDER=1 after funding the created account."
            )
            return

        print("7. Place a delegated order with the HMAC-scoped client.")
        token_id = str(market.tokens.yes)
        print(
            f"   Delegated order context: on_behalf_of={account.profile_id} "
            f"account={account.account}"
        )
        response = await scoped.delegated_orders.create_order(
            token_id=token_id,
            side=Side.BUY,
            order_type=OrderType.GTC,
            market_slug=market_slug,
            on_behalf_of=account.profile_id,
            price=float(os.getenv("LIMITLESS_DELEGATED_ORDER_PRICE", "0.05")),
            size=float(os.getenv("LIMITLESS_DELEGATED_ORDER_SIZE", "1")),
        )
        print(f"   Created delegated order: {response.order.id}")

        print("8. Cleanup delegated orders.")
        message = await scoped.delegated_orders.cancel_on_behalf_of(
            response.order.id,
            account.profile_id,
        )
        print(f"   Cancelled created delegated order: {message}")
        message = await scoped.delegated_orders.cancel_all_on_behalf_of(
            market_slug,
            account.profile_id,
        )
        print(f"   Cancelled remaining delegated orders for market: {message}")

    finally:
        await bootstrap.close()
        await scoped.close()


if __name__ == "__main__":
    asyncio.run(main())
