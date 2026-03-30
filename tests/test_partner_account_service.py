"""Tests for partner-account creation operations."""

from unittest.mock import AsyncMock, Mock

import pytest

from limitless_sdk.partner_accounts import PartnerAccountService
from limitless_sdk.types import (
    CreatePartnerAccountEOAHeaders,
    CreatePartnerAccountInput,
)


@pytest.mark.asyncio
async def test_create_account_server_wallet_mode_posts_without_eoa_headers():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.post_with_headers = AsyncMock(
        return_value={
            "profileId": 321,
            "account": "0x0000000000000000000000000000000000000321",
        }
    )

    service = PartnerAccountService(http_client)
    response = await service.create_account(
        CreatePartnerAccountInput(
            display_name="Server Wallet Bot",
            create_server_wallet=True,
        )
    )

    http_client.require_auth.assert_called_once_with("create_partner_account")
    http_client.post_with_headers.assert_awaited_once_with(
        "/profiles/partner-accounts",
        {"displayName": "Server Wallet Bot", "createServerWallet": True},
        headers=None,
    )
    assert response.profile_id == 321


@pytest.mark.asyncio
async def test_create_account_eoa_mode_sends_verification_headers():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.post_with_headers = AsyncMock(
        return_value={
            "profileId": 322,
            "account": "0x0000000000000000000000000000000000000322",
        }
    )

    service = PartnerAccountService(http_client)
    response = await service.create_account(
        CreatePartnerAccountInput(display_name="EOA Child"),
        CreatePartnerAccountEOAHeaders(
            account="0xchild",
            signingMessage="0x1234",
            signature="0xsig",
        ),
    )

    http_client.post_with_headers.assert_awaited_once_with(
        "/profiles/partner-accounts",
        {"displayName": "EOA Child"},
        headers={
            "x-account": "0xchild",
            "x-signing-message": "0x1234",
            "x-signature": "0xsig",
        },
    )
    assert response.profile_id == 322


@pytest.mark.asyncio
async def test_create_account_rejects_display_name_longer_than_44_chars():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.post_with_headers = AsyncMock()
    service = PartnerAccountService(http_client)

    with pytest.raises(ValueError) as exc:
        await service.create_account(
            CreatePartnerAccountInput(display_name="x" * 45, create_server_wallet=True)
        )

    assert "44 characters" in str(exc.value)
    http_client.post_with_headers.assert_not_called()


@pytest.mark.asyncio
async def test_create_account_requires_eoa_headers_when_server_wallet_false():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.post_with_headers = AsyncMock()
    service = PartnerAccountService(http_client)

    with pytest.raises(ValueError) as exc:
        await service.create_account(CreatePartnerAccountInput(display_name="EOA Child"))

    assert "eoa_headers are required" in str(exc.value)
    http_client.post_with_headers.assert_not_called()
