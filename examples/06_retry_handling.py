"""
Retry on 404 Example

Demonstrates retry_on_errors decorator with 3 retries on 404 status code.
"""

import asyncio
from limitless_sdk.api import HttpClient, retry_on_errors, APIError


async def main():
    http_client = HttpClient(base_url="https://httpbin.org")

    try:
        retry_count = {"attempts": 0}

        def on_retry(attempt: int, error: Exception, delay: float):
            retry_count["attempts"] = attempt + 1
            print(f"Retry {attempt + 1}/3 - waiting {delay}s...")

        @retry_on_errors(
            status_codes={404},
            max_retries=3,
            delays=[1, 2, 3],
            on_retry=on_retry,
        )
        async def fetch_404():
            print("Fetching /status/404...")
            return await http_client.get("/status/404")

        result = await fetch_404()
        print(f"Success: {result}")

    except APIError as e:
        print(f"\nFailed after {retry_count['attempts']} retries")
        print(f"Status: {e.status_code}")
    finally:
        await http_client.close()


if __name__ == "__main__":
    asyncio.run(main())
