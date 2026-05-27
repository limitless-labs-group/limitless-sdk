"""Tests for portfolio profile operations."""

from unittest.mock import AsyncMock, Mock

import pytest

from limitless_sdk.portfolio import PortfolioFetcher


@pytest.mark.asyncio
async def test_get_profile_uses_provided_address():
    http_client = Mock()
    http_client.get = AsyncMock(
        return_value={
            "id": 1,
            "account": "0x1234",
        }
    )

    fetcher = PortfolioFetcher(http_client)
    response = await fetcher.get_profile(" 0x1234 ")

    http_client.get.assert_awaited_once_with("/profiles/0x1234")
    assert response["id"] == 1
    assert response["account"] == "0x1234"


@pytest.mark.asyncio
async def test_get_current_profile_uses_authenticated_profile_endpoint():
    http_client = Mock()
    http_client.get = AsyncMock(
        return_value={
            "id": 570,
            "account": "0x1676716Ef7F19B5C5d690631CB57cf0bFD900A3d",
        }
    )

    fetcher = PortfolioFetcher(http_client)
    response = await fetcher.get_current_profile()

    http_client.get.assert_awaited_once_with("/profiles/me")
    assert response["id"] == 570


@pytest.mark.asyncio
async def test_get_profile_rejects_blank_address_before_network():
    http_client = Mock()
    http_client.get = AsyncMock()

    fetcher = PortfolioFetcher(http_client)

    with pytest.raises(ValueError, match="address must be a non-empty string"):
        await fetcher.get_profile(" ")

    http_client.get.assert_not_awaited()
