"""Server-wallet redeem and optional withdraw example using HMAC-scoped partner auth."""

import asyncio
import os

from limitless_sdk import (
    CreatePartnerAccountInput,
    PartnerWithdrawalAddressInput,
    ScopeAccountCreation,
    ScopeDelegatedSigning,
    ScopeTrading,
    ScopeWithdrawal,
)

from common import derive_scoped_client, ready_delay_ms, require_env, truthy_env


async def main() -> None:
    identity_token = require_env("LIMITLESS_IDENTITY_TOKEN")
    market_slug = require_env("MARKET_SLUG")
    bootstrap, scoped, derived = await derive_scoped_client(
        identity_token,
        [
            ScopeTrading,
            ScopeDelegatedSigning,
            ScopeAccountCreation,
            ScopeWithdrawal,
        ],
        label="python-sdk-server-wallet-example",
    )

    try:
        capabilities = await bootstrap.api_tokens.get_capabilities(identity_token)
        print(
            f"Capabilities: enabled={capabilities.token_management_enabled} "
            f"scopes={capabilities.allowed_scopes}"
        )

        market = await scoped.markets.get_market(market_slug)
        if not market.condition_id:
            raise ValueError(
                f"Market {market_slug} does not expose condition_id"
            )

        existing_profile_id = os.getenv("LIMITLESS_ON_BEHALF_OF")
        existing_account = os.getenv("LIMITLESS_SERVER_WALLET_ACCOUNT")

        if existing_profile_id:
            account_profile_id = int(existing_profile_id)
            account_address = existing_account or "(not provided)"
            print("Using existing server-wallet child account from env")
        else:
            account = await scoped.partner_accounts.create_account(
                CreatePartnerAccountInput(
                    display_name=os.getenv(
                        "PARTNER_ACCOUNT_DISPLAY_NAME", "Python SDK Server Wallet"
                    ),
                    create_server_wallet=True,
                )
            )
            account_profile_id = account.profile_id
            account_address = account.account

        print("Server-wallet redeem setup")
        print(
            f"  market={market.slug} condition_id={market.condition_id} "
            f"exchange={market.venue.exchange if market.venue else 'n/a'}"
        )
        print(
            f"  child_profile_id={account_profile_id} child_account={account_address}"
        )
        print(f"  derived_token_id={derived.token_id} scopes={derived.scopes}")
        print(
            "Check allowances with partner_accounts.check_allowances(); "
            "if retryable targets are missing or failed, call "
            "partner_accounts.retry_allowances() and poll again."
        )

        delay_ms = ready_delay_ms()
        if delay_ms > 0:
            print(f"Waiting {delay_ms}ms before checking server-wallet readiness...")
            await asyncio.sleep(delay_ms / 1000)

        redeem_response = await scoped.server_wallets.redeem_positions(
            condition_id=market.condition_id,
            on_behalf_of=account_profile_id,
        )
        print(
            "Redeem submitted:",
            f"transaction_id={redeem_response.transaction_id}",
            f"user_operation_hash={redeem_response.user_operation_hash}",
            f"wallet={redeem_response.wallet_address}",
        )

        if truthy_env("LIMITLESS_SKIP_WITHDRAW") or not os.getenv(
            "LIMITLESS_WITHDRAW_AMOUNT"
        ):
            print(
                "Skipping withdraw. Set LIMITLESS_SKIP_WITHDRAW=0 and "
                "LIMITLESS_WITHDRAW_AMOUNT to execute the withdraw step."
            )
            return

        amount = require_env("LIMITLESS_WITHDRAW_AMOUNT")
        destination = os.getenv("LIMITLESS_WITHDRAW_DESTINATION")
        allowlist_destination = truthy_env("LIMITLESS_ALLOWLIST_WITHDRAW_DESTINATION")
        destination_label = os.getenv("LIMITLESS_WITHDRAW_DESTINATION_LABEL", "treasury")
        token = os.getenv("LIMITLESS_WITHDRAW_TOKEN")

        print(
            "Withdrawing:",
            f"amount={amount}",
            f"token={token or '(default token)'}",
            "destination="
            f"{destination or '(default: authenticated smart wallet when present, otherwise account)'}",
        )

        if destination and allowlist_destination:
            print(
                "Allowlisting withdraw destination:",
                f"destination={destination}",
                f"label={destination_label}",
            )
            withdrawal_address = await bootstrap.partner_accounts.add_withdrawal_address(
                identity_token,
                PartnerWithdrawalAddressInput(
                    address=destination,
                    label=destination_label,
                ),
            )
            print(
                "Withdrawal destination allowlisted:",
                f"id={withdrawal_address.id}",
                f"profile_id={withdrawal_address.profile_id}",
                f"destination={withdrawal_address.destination_address}",
                f"label={withdrawal_address.label}",
            )

        withdraw_response = await scoped.server_wallets.withdraw(
            amount=amount,
            on_behalf_of=account_profile_id,
            token=token,
            destination=destination,
        )
        print(
            "Withdraw submitted:",
            f"transaction_id={withdraw_response.transaction_id}",
            f"user_operation_hash={withdraw_response.user_operation_hash}",
            f"destination={withdraw_response.destination}",
        )

    finally:
        await bootstrap.close()
        await scoped.close()


if __name__ == "__main__":
    asyncio.run(main())
