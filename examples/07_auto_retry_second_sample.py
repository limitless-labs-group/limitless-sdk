"""
Auto-Retry Example with RetryableClient

Demonstrates automatic retry logic for API calls using RetryableClient wrapper.
Shows how to handle transient failures like rate limits (429) and server errors (500, 503).

Setup:
    export LIMITLESS_API_KEY="your-api-key"

Features:
    - Automatic retry on configurable status codes (429, 500, 502, 503, 504)
    - Fixed delays or exponential backoff strategies
    - Callback hooks for monitoring retry attempts
    - RetryableClient wrapper for seamless retry integration
"""

import asyncio
import os
from dotenv import load_dotenv
from limitless_sdk.api import HttpClient, RetryableClient, RetryConfig, APIError
from limitless_sdk.portfolio import PortfolioFetcher
from limitless_sdk.types import ConsoleLogger, LogLevel

# Load environment variables
load_dotenv()

# Configuration
API_URL = os.getenv("API_URL", "https://api.limitless.exchange")
LIMITLESS_API_KEY = os.getenv("LIMITLESS_API_KEY")


async def main():
    # Validate API key
    if not LIMITLESS_API_KEY:
        raise ValueError(
            "Set LIMITLESS_API_KEY in .env file\n"
            "Get your API key from: https://limitless.exchange"
        )

    print("Auto-Retry Example with RetryableClient\n")

    # Create logger to see retry attempts
    logger = ConsoleLogger(level=LogLevel.INFO)

    # Create HTTP client with API key
    http_client = HttpClient(
        base_url=API_URL,
        api_key=LIMITLESS_API_KEY,
        logger=logger
    )

    try:
        # Example 1: RetryableClient with default config
        print("=" * 60)
        print("Example 1: Default retry configuration")
        print("=" * 60)
        print("Config: Retry on [429, 500, 502, 503, 504], max 3 attempts")
        print("Delays: Exponential backoff (1s, 2s, 4s)\n")

        # Default retry config
        default_config = RetryConfig()
        retryable_client = RetryableClient(
            http_client=http_client,
            retry_config=default_config,
            logger=logger
        )

        portfolio = PortfolioFetcher(retryable_client)
        positions = await portfolio.get_positions()

        print(f"✓ Request successful!")
        print(f"  CLOB positions: {len(positions.get('clob', []))}")
        print(f"  AMM positions: {len(positions.get('amm', []))}")
        print(f"  Accumulative points: {positions.get('accumulativePoints', 0)}\n")

        # Example 2: Custom retry config with fixed delays
        print("=" * 60)
        print("Example 2: Custom retry configuration")
        print("=" * 60)
        print("Config: Retry on [429, 500, 503], max 5 attempts")
        print("Delays: Fixed delays [2s, 5s, 10s, 15s, 20s]\n")

        retry_attempts = {"count": 0}

        def on_retry_callback(attempt: int, error: Exception, delay: float):
            """Callback invoked before each retry attempt."""
            retry_attempts["count"] = attempt + 1
            print(f"  ⚠️  Retry attempt {attempt + 1} - waiting {delay:.1f}s...")
            print(f"     Error: {error}")

        custom_config = RetryConfig(
            status_codes={429, 500, 503},
            max_retries=5,
            delays=[2, 5, 10, 15, 20],
            on_retry=on_retry_callback
        )

        custom_retryable = RetryableClient(
            http_client=http_client,
            retry_config=custom_config,
            logger=logger
        )

        portfolio2 = PortfolioFetcher(custom_retryable)
        history = await portfolio2.get_user_history(page=1, limit=5)

        print(f"✓ Request successful!")
        print(f"  Total history entries: {history.get('totalCount', 0)}")
        print(f"  Fetched: {len(history.get('data', []))} entries")
        if retry_attempts["count"] > 0:
            print(f"  Retry attempts: {retry_attempts['count']}")
        print()

        # Example 3: Exponential backoff with custom base
        print("=" * 60)
        print("Example 3: Exponential backoff with jitter")
        print("=" * 60)
        print("Config: Exponential base=3, max delay=30s")
        print("Delays: 3s, 9s, 27s (with ±20% jitter)\n")

        exponential_config = RetryConfig(
            status_codes={429, 500, 502, 503, 504},
            max_retries=3,
            exponential_base=3,
            max_delay=30,
        )

        exponential_retryable = RetryableClient(
            http_client=http_client,
            retry_config=exponential_config,
            logger=logger
        )

        # Make a simple GET request
        positions3 = await exponential_retryable.get("/portfolio/positions")
        print(f"✓ Request successful!")
        print(f"  Response received with {len(positions3.get('clob', []))} CLOB positions\n")

        # Example 4: Long-running application pattern
        print("=" * 60)
        print("Example 4: Long-running application pattern")
        print("=" * 60)
        print("Simulating multiple API calls over time...")
        print("(RetryableClient handles transient failures automatically)\n")

        long_running_client = RetryableClient(
            http_client=http_client,
            retry_config=RetryConfig(max_retries=3),
            logger=logger
        )

        portfolio_fetcher = PortfolioFetcher(long_running_client)

        for i in range(3):
            print(f"Iteration {i + 1}/3:")
            try:
                positions = await portfolio_fetcher.get_positions()
                print(f"  ✓ Fetched {len(positions.get('clob', []))} CLOB positions")
                print(f"  ✓ Fetched {len(positions.get('amm', []))} AMM positions\n")
            except APIError as e:
                print(f"  ✗ Failed after retries: {e.status_code} - {e.message}\n")

            await asyncio.sleep(1)

        print("=" * 60)
        print("Summary")
        print("=" * 60)
        print("RetryableClient automatically:")
        print("  1. Detects transient failures (429, 500, 502, 503, 504)")
        print("  2. Applies exponential backoff with jitter")
        print("  3. Retries failed requests transparently")
        print("  4. Invokes callbacks for monitoring")
        print("\nBenefits:")
        print("  - No manual retry logic needed")
        print("  - Handles rate limits gracefully")
        print("  - Prevents thundering herd with jitter")
        print("  - Customizable per use case")

    except APIError as e:
        print(f"\n✗ API Error: {e.status_code} - {e.message}")
        if e.status_code == 401:
            print("  Check your LIMITLESS_API_KEY")
    finally:
        await http_client.close()
        print("\nHTTP client closed")


if __name__ == "__main__":
    asyncio.run(main())
