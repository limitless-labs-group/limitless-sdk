"""
Auto-Retry Example


Setup:
    export PRIVATE_KEY="0x..." as we need to fetch positions
"""

import asyncio
import os
from dotenv import load_dotenv
from eth_account import Account
from limitless_sdk.api import HttpClient
from limitless_sdk.auth import MessageSigner, Authenticator, AuthenticatedClient
from limitless_sdk.portfolio import PortfolioFetcher
from limitless_sdk.types import LoginOptions

# Load environment variables
load_dotenv()

# Configuration
API_URL = os.getenv("API_URL", "https://api.limitless.exchange")


async def main():
    # Setup
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        raise ValueError("Set PRIVATE_KEY in .env file")

    account = Account.from_key(private_key)
    print(f"Wallet: {account.address}\n")

    http_client = HttpClient(base_url=API_URL)

    try:
        # Authenticate
        signer = MessageSigner(account)
        authenticator = Authenticator(http_client, signer)
        result = await authenticator.authenticate(LoginOptions(client="eoa"))

        print(f"Authenticated: {result.profile.account}")
        print(f"Session: {result.session_cookie[:20]}...\n")

        # Create AuthenticatedClient wrapper
        auth_client = AuthenticatedClient(
            http_client=http_client,
            authenticator=authenticator
        )

        portfolio_fetcher = PortfolioFetcher(http_client)

        # Example 1: Normal request with valid session
        print("Example 1: Normal request")
        response = await auth_client.with_retry(
            lambda: portfolio_fetcher.get_positions()
        )
        print(f"✓ CLOB positions: {len(response['clob'])}")
        print(f"✓ Points: {response['accumulativePoints']}\n")

        # Example 2: Simulate session expiration
        print("Example 2: Auto-retry after session expiration")
        http_client.set_session_cookie(None)  # Simulate expiration
        print("Session cleared (simulated expiration)")

        response = await auth_client.with_retry(
            lambda: portfolio_fetcher.get_positions()
        )
        print(f"✓ Auto re-authenticated and retried")
        print(f"✓ CLOB positions: {len(response['clob'])}\n")

        # Example 3: Long-running pattern
        print("Example 3: Long-running application pattern")
        for i in range(3):
            # Simulate session expiration every other iteration
            if i % 2 == 1:
                http_client.set_session_cookie(None)
                print(f"Iteration {i+1}: Session expired")
            else:
                print(f"Iteration {i+1}: Session valid")

            response = await auth_client.with_retry(
                lambda: portfolio_fetcher.get_positions()
            )
            print(f"  ✓ Fetched {len(response['clob'])} positions\n")

            await asyncio.sleep(1)

        print("AuthenticatedClient automatically:")
        print("  1. Detects auth failures (401/403)")
        print("  2. Re-authenticates transparently")
        print("  3. Retries the original request")

    finally:
        await http_client.close()


if __name__ == "__main__":
    asyncio.run(main())
