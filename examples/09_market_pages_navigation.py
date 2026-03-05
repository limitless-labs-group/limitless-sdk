"""
Market Pages Navigation Example

Covers all MarketPageFetcher methods:
1) get_navigation()
2) get_market_page_by_path(path)
3) get_markets(page_id, params) - offset, single ticker, two tickers, cursor
4) get_property_keys()
5) get_property_key(id)
6) get_property_options(key_id, parent_id=None)
"""

import asyncio
from pprint import pprint

from limitless_sdk.api import HttpClient
from limitless_sdk.market_pages import MarketPageFetcher


API_URL = "https://api.limitless.exchange"


def find_first_path(nodes):
    """Find first available path recursively."""
    for node in nodes:
        if node.path:
            return node.path
        if node.children:
            child_path = find_first_path(node.children)
            if child_path:
                return child_path
    return None


def log_raw(title, data):
    print(f"\n{title}")
    pprint(data, depth=None, sort_dicts=False)


async def main():
    http_client = HttpClient(base_url=API_URL)
    page_fetcher = MarketPageFetcher(http_client)

    try:
        print("=== Market Pages: full API example ===")

        navigation = await page_fetcher.get_navigation()
        log_raw("1) get_navigation() -> raw response:", navigation)

        crypto_node = next((n for n in navigation if n.path == "/crypto"), None)
        page_path = crypto_node.path if crypto_node else (find_first_path(navigation) or "/")

        page = await page_fetcher.get_market_page_by_path(page_path)
        log_raw(f"2) get_market_page_by_path({page_path}) -> raw response:", page)

        offset_markets = await page_fetcher.get_markets(
            page.id,
            {
                "page": 1,
                "limit": 10,
                "sort": "-updatedAt",
            },
        )
        log_raw("3a) get_markets() with page/limit (offset pagination):", offset_markets)

        single_ticker = await page_fetcher.get_markets(
            page.id,
            {
                "limit": 10,
                "sort": "-updatedAt",
                "filters": {"ticker": "btc"},
            },
        )
        log_raw("3b) get_markets() with single ticker (btc):", single_ticker)

        two_tickers = await page_fetcher.get_markets(
            page.id,
            {
                "limit": 10,
                "sort": "-updatedAt",
                "filters": {"ticker": ["btc", "eth"]},
            },
        )
        log_raw("3c) get_markets() with two tickers (btc + eth):", two_tickers)

        try:
            cursor_page_1 = await page_fetcher.get_markets(
                page.id,
                {
                    "cursor": "",
                    "limit": 10,
                    "sort": "-updatedAt",
                },
            )
            log_raw("3d) get_markets() with cursor pagination - page 1:", cursor_page_1)

            if getattr(cursor_page_1, "cursor", None) and cursor_page_1.cursor.next_cursor:
                cursor_page_2 = await page_fetcher.get_markets(
                    page.id,
                    {
                        "cursor": cursor_page_1.cursor.next_cursor,
                        "limit": 10,
                        "sort": "-updatedAt",
                    },
                )
                log_raw("3d) get_markets() with cursor pagination - page 2:", cursor_page_2)
            else:
                print("\nNo next cursor returned for this page/filter set.")
        except Exception as err:
            print("\nCursor pagination is not available for this page/filter set.")
            print(f"Reason: {err}")

        property_keys = await page_fetcher.get_property_keys()
        log_raw("4) get_property_keys() -> raw response:", property_keys)

        if not property_keys:
            print("\nNo property keys returned - skipping property-key details.")
            return

        first_key_id = property_keys[0].id
        property_key = await page_fetcher.get_property_key(first_key_id)
        log_raw(f"5) get_property_key({first_key_id}) -> raw response:", property_key)

        root_options = await page_fetcher.get_property_options(property_key.id)
        log_raw(f"6) get_property_options({property_key.id}) -> root options:", root_options)

        if root_options:
            parent_option_id = root_options[0].id
            child_options = await page_fetcher.get_property_options(property_key.id, parent_option_id)
            log_raw(
                f"6b) get_property_options({property_key.id}, {parent_option_id}) -> child options:",
                child_options,
            )
        else:
            print("\nNo root options available for child-options example.")

        print("\n✅ market-pages example completed")
    finally:
        await http_client.close()


if __name__ == "__main__":
    asyncio.run(main())

