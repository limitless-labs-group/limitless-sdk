"""Tests for market-pages fetcher."""

import pytest
from unittest.mock import AsyncMock

from limitless_sdk.market_pages import MarketPageFetcher
from limitless_sdk.types.market_pages import (
    MarketPageMarketsCursorResponse,
    MarketPageMarketsOffsetResponse,
)


def _market_payload(market_id: int = 1, slug: str = "bitcoin-test") -> dict:
    return {
        "id": market_id,
        "slug": slug,
        "title": "Bitcoin Test Market",
        "collateralToken": {
            "address": "0x123",
            "decimals": 6,
            "symbol": "USDC",
        },
        "expirationDate": "2026-12-31T00:00:00.000Z",
        "expirationTimestamp": 1798675200000,
        "createdAt": "2026-01-01T00:00:00.000Z",
        "updatedAt": "2026-01-01T00:00:00.000Z",
        "categories": [],
        "status": "FUNDED",
        "creator": {"name": "Limitless"},
        "tags": [],
        "tradeType": "clob",
        "marketType": "single",
        "priorityIndex": 0,
        "metadata": {"fee": False},
    }


def _page_payload(page_id: str = "page-1") -> dict:
    return {
        "id": page_id,
        "name": "Crypto",
        "slug": "crypto",
        "fullPath": "/crypto",
        "description": None,
        "baseFilter": {},
        "filterGroups": [],
        "metadata": {},
        "breadcrumb": [],
    }


@pytest.mark.asyncio
async def test_get_navigation_returns_typed_nodes():
    http_client = AsyncMock()
    http_client.get.return_value = [
        {"id": "1", "name": "Crypto", "slug": "crypto", "path": "/crypto", "children": []}
    ]

    fetcher = MarketPageFetcher(http_client)
    result = await fetcher.get_navigation()

    assert len(result) == 1
    assert result[0].path == "/crypto"
    http_client.get.assert_awaited_once_with("/navigation")


@pytest.mark.asyncio
async def test_get_market_page_by_path_success():
    http_client = AsyncMock()
    http_client.get_raw.return_value = AsyncMock(
        status=200,
        headers={},
        data=_page_payload("page-success"),
    )

    fetcher = MarketPageFetcher(http_client)
    page = await fetcher.get_market_page_by_path("/crypto")

    assert page.id == "page-success"
    assert page.full_path == "/crypto"


@pytest.mark.asyncio
async def test_get_market_page_by_path_follows_redirect():
    http_client = AsyncMock()
    http_client.get_raw.side_effect = [
        AsyncMock(status=301, headers={"location": "/crypto"}, data=""),
        AsyncMock(status=200, headers={}, data=_page_payload("page-redirected")),
    ]

    fetcher = MarketPageFetcher(http_client)
    page = await fetcher.get_market_page_by_path("/old-crypto")

    assert page.id == "page-redirected"
    assert http_client.get_raw.await_count == 2


@pytest.mark.asyncio
async def test_get_market_page_by_path_missing_location_raises():
    http_client = AsyncMock()
    http_client.get_raw.return_value = AsyncMock(status=301, headers={}, data="")

    fetcher = MarketPageFetcher(http_client)
    with pytest.raises(RuntimeError, match="Location header"):
        await fetcher.get_market_page_by_path("/missing-location")


@pytest.mark.asyncio
async def test_get_market_page_by_path_redirect_depth_limit():
    http_client = AsyncMock()
    http_client.get_raw.side_effect = [
        AsyncMock(status=301, headers={"location": "/r1"}, data=""),
        AsyncMock(status=301, headers={"location": "/r2"}, data=""),
        AsyncMock(status=301, headers={"location": "/r3"}, data=""),
        AsyncMock(status=301, headers={"location": "/r4"}, data=""),
    ]

    fetcher = MarketPageFetcher(http_client)
    with pytest.raises(RuntimeError, match="Too many redirects"):
        await fetcher.get_market_page_by_path("/r0")


@pytest.mark.asyncio
async def test_get_markets_returns_offset_response_and_serializes_filters():
    http_client = AsyncMock()
    http_client.get.return_value = {
        "data": [_market_payload()],
        "pagination": {"page": 1, "limit": 10, "total": 100, "totalPages": 10},
    }

    fetcher = MarketPageFetcher(http_client)
    response = await fetcher.get_markets(
        "page-id",
        {
            "page": 1,
            "limit": 10,
            "sort": "-updatedAt",
            "filters": {"ticker": "btc"},
        },
    )

    assert isinstance(response, MarketPageMarketsOffsetResponse)
    assert response.data[0].slug == "bitcoin-test"
    called_endpoint = http_client.get.await_args.args[0]
    assert called_endpoint.startswith("/market-pages/page-id/markets?")
    assert "ticker=btc" in called_endpoint
    assert "sort=-updatedAt" in called_endpoint


@pytest.mark.asyncio
async def test_get_markets_returns_cursor_response_and_serializes_array_filters():
    http_client = AsyncMock()
    http_client.get.return_value = {
        "data": [_market_payload(2, "ethereum-test")],
        "cursor": {"nextCursor": "cursor-1"},
    }

    fetcher = MarketPageFetcher(http_client)
    response = await fetcher.get_markets(
        "page-id",
        {
            "cursor": "",
            "limit": 10,
            "sort": "-updatedAt",
            "filters": {"ticker": ["btc", "eth"]},
        },
    )

    assert isinstance(response, MarketPageMarketsCursorResponse)
    assert response.cursor.next_cursor == "cursor-1"
    called_endpoint = http_client.get.await_args.args[0]
    assert "ticker=btc" in called_endpoint
    assert "ticker=eth" in called_endpoint


@pytest.mark.asyncio
async def test_get_markets_rejects_page_and_cursor_together():
    http_client = AsyncMock()
    fetcher = MarketPageFetcher(http_client)

    with pytest.raises(ValueError, match="mutually exclusive"):
        await fetcher.get_markets(
            "page-id",
            {
                "page": 1,
                "cursor": "abc",
            },
        )


@pytest.mark.asyncio
async def test_get_markets_invalid_shape_raises():
    http_client = AsyncMock()
    http_client.get.return_value = {"data": []}

    fetcher = MarketPageFetcher(http_client)
    with pytest.raises(RuntimeError, match="expected `pagination` or `cursor`"):
        await fetcher.get_markets("page-id")


@pytest.mark.asyncio
async def test_property_key_endpoints():
    http_client = AsyncMock()
    http_client.get.side_effect = [
        [
            {
                "id": "k1",
                "name": "Ticker",
                "slug": "ticker",
                "type": "multi-select",
                "metadata": {},
                "isSystem": False,
                "createdAt": "2026-01-01T00:00:00.000Z",
                "updatedAt": "2026-01-01T00:00:00.000Z",
                "options": [],
            }
        ],
        {
            "id": "k1",
            "name": "Ticker",
            "slug": "ticker",
            "type": "multi-select",
            "metadata": {},
            "isSystem": False,
            "createdAt": "2026-01-01T00:00:00.000Z",
            "updatedAt": "2026-01-01T00:00:00.000Z",
            "options": [],
        },
        [],
        [],
    ]

    fetcher = MarketPageFetcher(http_client)

    keys = await fetcher.get_property_keys()
    assert keys[0].id == "k1"

    key = await fetcher.get_property_key("k1")
    assert key.slug == "ticker"

    await fetcher.get_property_options("k1")
    await fetcher.get_property_options("k1", "parent-1")

    assert http_client.get.await_args_list[2].args[0] == "/property-keys/k1/options"
    assert http_client.get.await_args_list[3].args[0] == "/property-keys/k1/options?parentId=parent-1"

