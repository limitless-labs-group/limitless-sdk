"""
Basic Authentication Example

Demonstrates minimal authentication flow with EOA (Externally Owned Account).
Also shows how to add custom HTTP headers.

Setup:
    Option 1: Environment variable
        export PRIVATE_KEY="0x..."

    Option 2: Direct assignment (line 25)
        private_key = "0x..."

Custom Headers:
    Global headers (applied to ALL requests):
        HttpClient(additional_headers={"X-Custom": "value"})

    Per-request headers (applied to single request):
        http_client.get("/path", headers={"X-Request-ID": "123"})

Logging:
    Enable DEBUG logging to see all request headers:
        logger = ConsoleLogger(level=LogLevel.DEBUG)
        HttpClient(logger=logger)
"""

import asyncio
import os
from dotenv import load_dotenv
from eth_account import Account
from limitless_sdk.api import HttpClient, APIError
from limitless_sdk.auth import MessageSigner, Authenticator
from limitless_sdk.types import LoginOptions, ConsoleLogger, LogLevel

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
    print(f"Authenticating: {account.address}\n")

    # Create logger to see headers in requests
    # LogLevel.DEBUG - shows all headers (except cookies for security)
    # LogLevel.INFO - shows basic request info
    logger = ConsoleLogger(level=LogLevel.DEBUG)

    # Create HTTP client
    # Optional: Add custom headers to ALL requests (GET, POST, DELETE, etc.)
    http_client = HttpClient(
        base_url=API_URL,
        additional_headers={
            "X-Custom-Header": "my-value",
            "X-API-Version": "v1",
        },
        logger=logger
    )

    try:
        # Authenticate (EOA)
        signer = MessageSigner(account)
        authenticator = Authenticator(http_client, signer)

        result = await authenticator.authenticate(LoginOptions(client="eoa"))

        # Show credentials
        print(f"\nAuthentication successful!")
        print(f"User ID: {result.profile.id}")
        print(f"Session Cookie: {result.session_cookie[:32]}...")

        # Optional: Add per-request headers (in addition to global headers)
        # Example with error handling:
        # try:
        #     await http_client.get("/some-endpoint", headers={"X-Request-ID": "123"})
        # except APIError as e:
        #     print(f"API Error: {e.status_code} - {e.message}")

    finally:
        await http_client.close()


if __name__ == "__main__":
    asyncio.run(main())
