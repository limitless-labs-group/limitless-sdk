"""Partner self-service API-token example."""

import asyncio

from limitless_sdk import ScopeTrading

from common import derive_scoped_client, require_env, truthy_env


async def main() -> None:
    identity_token = require_env("LIMITLESS_IDENTITY_TOKEN")
    bootstrap, scoped, derived = await derive_scoped_client(
        identity_token,
        [ScopeTrading],
        label="python-sdk-api-token-example",
    )

    try:
        capabilities = await bootstrap.api_tokens.get_capabilities(identity_token)
        print("Partner capabilities")
        print(
            f"  enabled={capabilities.token_management_enabled} "
            f"allowed_scopes={capabilities.allowed_scopes}"
        )

        print("Derived scoped token")
        print(
            f"  token_id={derived.token_id} "
            f"profile_id={derived.profile.id} scopes={derived.scopes}"
        )

        active_tokens = await scoped.api_tokens.list_tokens()
        print(f"Active scoped tokens visible through HMAC auth: {len(active_tokens)}")

        if truthy_env("LIMITLESS_REVOKE_DERIVED_TOKEN"):
            message = await scoped.api_tokens.revoke_token(derived.token_id)
            print(f"Revoked derived token: {message}")
        else:
            print("Skipping revoke step. Set LIMITLESS_REVOKE_DERIVED_TOKEN=1 to revoke it.")

    finally:
        await bootstrap.close()
        await scoped.close()


if __name__ == "__main__":
    asyncio.run(main())
