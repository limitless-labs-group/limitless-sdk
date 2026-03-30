"""WebSocket example using HMAC-scoped partner auth."""

import asyncio

from limitless_sdk import ScopeTrading

from common import derive_scoped_client, require_env


async def main() -> None:
    identity_token = require_env("LIMITLESS_IDENTITY_TOKEN")
    market_slug = require_env("MARKET_SLUG")
    bootstrap, scoped, derived = await derive_scoped_client(
        identity_token,
        [ScopeTrading],
        label="python-sdk-websocket-hmac-example",
    )

    ws_client = scoped.new_websocket_client()

    try:
        print("Derived scoped token")
        print(
            f"  token_id={derived.token_id} profile_id={derived.profile.id} scopes={derived.scopes}"
        )

        await ws_client.connect()
        print("Connected websocket client with shared HMAC auth.")

        await ws_client.subscribe("subscribe_positions", {"marketSlugs": [market_slug]})
        print(f"Subscribed to positions for {market_slug}. Waiting 5s for events...")
        await asyncio.sleep(5)

    finally:
        await ws_client.disconnect()
        await bootstrap.close()
        await scoped.close()


if __name__ == "__main__":
    asyncio.run(main())
