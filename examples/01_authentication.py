"""
Basic Authentication Example

Demonstrates minimal authentication flow with EOA (Externally Owned Account).

Setup:
    Option 1: Environment variable
        export PRIVATE_KEY="0x..."

    Option 2: Direct assignment (line 25)
        private_key = "0x..."
"""

import asyncio
import os
from dotenv import load_dotenv
from eth_account import Account
from limitless_sdk.api import HttpClient
from limitless_sdk.auth import MessageSigner, Authenticator
from limitless_sdk.types import LoginOptions

# Load environment variables from .env file
load_dotenv()

# Configuration
API_URL = "https://api.limitless.exchange"


async def main():
    # Setup - either from environment or set directly
    private_key = os.getenv("PRIVATE_KEY") or None  # Or set directly: "0x..."
    if not private_key:
        raise ValueError("Set PRIVATE_KEY in .env file or assign directly in code")

    account = Account.from_key(private_key)
    print(f"Authenticating: {account.address}")

    # Create HTTP client
    http_client = HttpClient(base_url=API_URL)

    try:
        # Authenticate (EOA)
        signer = MessageSigner(account)
        authenticator = Authenticator(http_client, signer)

        result = await authenticator.authenticate(LoginOptions(client="eoa"))

        # Show credentials
        print(f"\nAuthentication successful!")
        print(f"User ID: {result.profile.id}")
        print(f"Session Cookie: {result.session_cookie[:32]}...")

    finally:
        await http_client.close()


if __name__ == "__main__":
    asyncio.run(main())
