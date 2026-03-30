"""Tests for partner self-service api-token operations."""

from unittest.mock import AsyncMock, Mock

import pytest

from limitless_sdk.api_tokens import ApiTokenService
from limitless_sdk.types import DeriveApiTokenInput


@pytest.mark.asyncio
async def test_get_capabilities_uses_identity_auth():
    http_client = Mock()
    http_client.get_with_identity = AsyncMock(
        return_value={
            "partnerProfileId": 167,
            "tokenManagementEnabled": True,
            "allowedScopes": ["trading", "delegated_signing"],
        }
    )

    service = ApiTokenService(http_client)
    response = await service.get_capabilities("identity-token")

    http_client.get_with_identity.assert_awaited_once_with(
        "/auth/api-tokens/capabilities",
        "identity-token",
    )
    assert response.partner_profile_id == 167
    assert response.token_management_enabled is True
    assert response.allowed_scopes == ["trading", "delegated_signing"]


@pytest.mark.asyncio
async def test_derive_token_posts_expected_payload():
    http_client = Mock()
    http_client.post_with_identity = AsyncMock(
        return_value={
            "apiKey": "token-123",
            "secret": "secret",
            "tokenId": "token-123",
            "createdAt": "2026-03-30T12:00:00.000Z",
            "scopes": ["trading"],
            "profile": {"id": 167, "account": "0xabc"},
        }
    )

    service = ApiTokenService(http_client)
    response = await service.derive_token(
        "identity-token",
        DeriveApiTokenInput(label="bot", scopes=["trading"]),
    )

    http_client.post_with_identity.assert_awaited_once_with(
        "/auth/api-tokens/derive",
        "identity-token",
        {"label": "bot", "scopes": ["trading"]},
    )
    assert response.token_id == "token-123"
    assert response.api_key == "token-123"


@pytest.mark.asyncio
async def test_list_tokens_requires_auth_and_parses_items():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.get = AsyncMock(
        return_value=[
            {
                "tokenId": "token-123",
                "label": "bot",
                "scopes": ["trading"],
                "createdAt": "2026-03-30T12:00:00.000Z",
                "lastUsedAt": None,
            }
        ]
    )

    service = ApiTokenService(http_client)
    response = await service.list_tokens()

    http_client.require_auth.assert_called_once_with("list_tokens")
    http_client.get.assert_awaited_once_with("/auth/api-tokens")
    assert len(response) == 1
    assert response[0].token_id == "token-123"
    assert response[0].scopes == ["trading"]


@pytest.mark.asyncio
async def test_revoke_token_returns_message():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.delete = AsyncMock(return_value={"message": "Token revoked"})

    service = ApiTokenService(http_client)
    message = await service.revoke_token("token-123")

    http_client.require_auth.assert_called_once_with("revoke_token")
    http_client.delete.assert_awaited_once()
    assert message == "Token revoked"


@pytest.mark.asyncio
async def test_revoke_token_url_encodes_special_characters():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.delete = AsyncMock(return_value={"message": "Token revoked"})

    service = ApiTokenService(http_client)
    message = await service.revoke_token("token/with space")

    http_client.delete.assert_awaited_once_with("/auth/api-tokens/token%2Fwith%20space")
    assert message == "Token revoked"
