"""Tests for partner-account creation operations."""

from unittest.mock import AsyncMock, Mock

import pytest

from limitless_sdk.api import ConflictError, RateLimitError
from limitless_sdk.partner_accounts import PartnerAccountService
from limitless_sdk.types import (
    CreatePartnerAccountEOAHeaders,
    CreatePartnerAccountInput,
)

ALLOWANCE_RESPONSE = {
    "profileId": 12345,
    "partnerProfileId": 999,
    "chainId": 8453,
    "walletAddress": "0x1111111111111111111111111111111111111111",
    "ready": False,
    "summary": {
        "total": 1,
        "confirmed": 0,
        "missing": 0,
        "submitted": 1,
        "failed": 0,
    },
    "targets": [
        {
            "type": "USDC_ALLOWANCE",
            "tokenAddress": "0x2222222222222222222222222222222222222222",
            "spenderOrOperator": "0x3333333333333333333333333333333333333333",
            "label": "ctf-exchange",
            "requiredFor": "BUY",
            "confirmed": False,
            "status": "submitted",
            "transactionId": "privy-transaction-id",
            "txHash": "0xabc",
            "userOperationHash": "0xdef",
            "retryable": False,
        }
    ],
}


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


@pytest.mark.asyncio
async def test_check_allowances_gets_partner_account_allowance_state():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.get_hmac_credentials = Mock(
        return_value={"token_id": "token-1", "secret": "secret-1"}
    )
    http_client.get = AsyncMock(return_value=ALLOWANCE_RESPONSE)

    service = PartnerAccountService(http_client)
    response = await service.check_allowances(12345)

    http_client.require_auth.assert_called_once_with(
        "check_partner_account_allowances"
    )
    http_client.get.assert_awaited_once_with(
        "/profiles/partner-accounts/12345/allowances"
    )
    assert response.profile_id == 12345
    assert response.partner_profile_id == 999
    assert response.summary.submitted == 1
    assert response.targets[0].transaction_id == "privy-transaction-id"


@pytest.mark.asyncio
async def test_retry_allowances_posts_empty_body():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.get_hmac_credentials = Mock(
        return_value={"token_id": "token-1", "secret": "secret-1"}
    )
    http_client.post = AsyncMock(return_value=ALLOWANCE_RESPONSE)

    service = PartnerAccountService(http_client)
    response = await service.retry_allowances(12345)

    http_client.require_auth.assert_called_once_with(
        "retry_partner_account_allowances"
    )
    http_client.post.assert_awaited_once_with(
        "/profiles/partner-accounts/12345/allowances/retry",
        {},
    )
    assert response.profile_id == 12345
    assert response.targets[0].type == "USDC_ALLOWANCE"


@pytest.mark.asyncio
async def test_retry_allowances_propagates_rate_limit_and_conflict_errors():
    rate_limit_error = RateLimitError(
        "rate limited",
        status_code=429,
        response_data={"message": "rate limited", "retryAfterSeconds": 42},
        url="/profiles/partner-accounts/12345/allowances/retry",
        method="POST",
    )
    conflict_error = ConflictError(
        "allowance retry already running",
        status_code=409,
        response_data={"message": "allowance retry already running"},
        url="/profiles/partner-accounts/67890/allowances/retry",
        method="POST",
    )
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.get_hmac_credentials = Mock(
        return_value={"token_id": "token-1", "secret": "secret-1"}
    )
    http_client.post = AsyncMock(side_effect=[rate_limit_error, conflict_error])

    service = PartnerAccountService(http_client)

    with pytest.raises(RateLimitError) as rate_exc:
        await service.retry_allowances(12345)
    assert rate_exc.value.status_code == 429
    assert rate_exc.value.response_data["retryAfterSeconds"] == 42

    with pytest.raises(ConflictError) as conflict_exc:
        await service.retry_allowances(67890)
    assert conflict_exc.value.status_code == 409


@pytest.mark.asyncio
async def test_allowances_reject_invalid_profile_id_before_network():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.get_hmac_credentials = Mock(
        return_value={"token_id": "token-1", "secret": "secret-1"}
    )
    http_client.get = AsyncMock()
    http_client.post = AsyncMock()

    service = PartnerAccountService(http_client)

    with pytest.raises(ValueError, match="profile_id must be a positive integer"):
        await service.check_allowances(0)

    with pytest.raises(ValueError, match="profile_id must be a positive integer"):
        await service.retry_allowances(-1)

    http_client.get.assert_not_awaited()
    http_client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_allowances_reject_legacy_api_key_only_auth():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.get_hmac_credentials = Mock(return_value=None)
    http_client.get = AsyncMock()
    http_client.post = AsyncMock()

    service = PartnerAccountService(http_client)

    with pytest.raises(
        ValueError,
        match=(
            "Partner account allowance recovery requires HMAC-scoped API token auth; "
            "legacy API keys are not supported."
        ),
    ):
        await service.check_allowances(12345)

    with pytest.raises(
        ValueError,
        match=(
            "Partner account allowance recovery requires HMAC-scoped API token auth; "
            "legacy API keys are not supported."
        ),
    ):
        await service.retry_allowances(12345)

    http_client.get.assert_not_awaited()
    http_client.post.assert_not_awaited()
