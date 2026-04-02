"""Partner server-wallet account creation example."""

import asyncio
import os

from limitless_sdk import (
    CreatePartnerAccountInput,
    ScopeAccountCreation,
    ScopeTrading,
)

from common import derive_scoped_client, require_env


async def main() -> None:
    identity_token = require_env("LIMITLESS_IDENTITY_TOKEN")
    bootstrap, scoped, derived = await derive_scoped_client(
        identity_token,
        [ScopeTrading, ScopeAccountCreation],
        label="python-sdk-partner-account-example",
    )

    try:
        account = await scoped.partner_accounts.create_account(
            CreatePartnerAccountInput(
                display_name=os.getenv("PARTNER_ACCOUNT_DISPLAY_NAME", "Python SDK Bot"),
                create_server_wallet=True,
            )
        )

        print("Derived scoped token")
        print(
            f"  token_id={derived.token_id} "
            f"profile_id={derived.profile.id} scopes={derived.scopes}"
        )
        print("Created partner server-wallet account")
        print(f"  profile_id={account.profile_id} account={account.account}")
        print("Fund this account before attempting delegated trading.")

    finally:
        await bootstrap.close()
        await scoped.close()


if __name__ == "__main__":
    asyncio.run(main())
