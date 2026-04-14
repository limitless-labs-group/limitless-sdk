"""Tests for server-managed wallet operations."""

from unittest.mock import AsyncMock, Mock

import pytest

from limitless_sdk.server_wallets import ServerWalletService


VALID_CONDITION_ID = "0x" + ("ab" * 32)
VALID_ADDRESS = "0x1234567890123456789012345678901234567890"


@pytest.mark.asyncio
async def test_redeem_positions_posts_expected_payload():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.get_hmac_credentials = Mock(
        return_value={"token_id": "token-1", "secret": "secret-1"}
    )
    http_client.post = AsyncMock(
        return_value={
            "hash": "",
            "userOperationHash": "0xuserop",
            "transactionId": "tx-1",
            "walletAddress": VALID_ADDRESS,
            "conditionId": VALID_CONDITION_ID,
            "marketId": 42,
        }
    )

    service = ServerWalletService(http_client)
    response = await service.redeem_positions(
        condition_id=VALID_CONDITION_ID,
        on_behalf_of=326,
    )

    http_client.require_auth.assert_called_once_with(
        "redeem_server_wallet_positions"
    )
    http_client.post.assert_awaited_once_with(
        "/portfolio/redeem",
        {
            "conditionId": VALID_CONDITION_ID,
            "onBehalfOf": 326,
        },
    )
    assert response.market_id == 42
    assert response.wallet_address == VALID_ADDRESS


@pytest.mark.asyncio
async def test_withdraw_posts_expected_payload():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.get_hmac_credentials = Mock(
        return_value={"token_id": "token-1", "secret": "secret-1"}
    )
    http_client.post = AsyncMock(
        return_value={
            "hash": "",
            "userOperationHash": "0xuserop",
            "transactionId": "tx-2",
            "walletAddress": VALID_ADDRESS,
            "token": VALID_ADDRESS,
            "destination": VALID_ADDRESS,
            "amount": "5000000",
        }
    )

    service = ServerWalletService(http_client)
    response = await service.withdraw(
        amount="5000000",
        on_behalf_of=326,
    )

    http_client.require_auth.assert_called_once_with(
        "withdraw_server_wallet_funds"
    )
    http_client.post.assert_awaited_once_with(
        "/portfolio/withdraw",
        {
            "amount": "5000000",
            "onBehalfOf": 326,
        },
    )
    assert response.amount == "5000000"


@pytest.mark.asyncio
async def test_redeem_rejects_invalid_condition_id_before_network():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.get_hmac_credentials = Mock(
        return_value={"token_id": "token-1", "secret": "secret-1"}
    )
    http_client.post = AsyncMock()

    service = ServerWalletService(http_client)

    with pytest.raises(
        ValueError,
        match="condition_id must be a 0x-prefixed 32-byte hex string",
    ):
        await service.redeem_positions(
            condition_id="0x1234",
            on_behalf_of=326,
        )

    http_client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_withdraw_rejects_invalid_amount_before_network():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.get_hmac_credentials = Mock(
        return_value={"token_id": "token-1", "secret": "secret-1"}
    )
    http_client.post = AsyncMock()

    service = ServerWalletService(http_client)

    with pytest.raises(
        ValueError,
        match="amount must be a positive integer string in the token smallest unit",
    ):
        await service.withdraw(amount="0", on_behalf_of=326)

    http_client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_withdraw_rejects_invalid_addresses_before_network():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.get_hmac_credentials = Mock(
        return_value={"token_id": "token-1", "secret": "secret-1"}
    )
    http_client.post = AsyncMock()

    service = ServerWalletService(http_client)

    with pytest.raises(ValueError, match="token must be a valid EVM address"):
        await service.withdraw(
            amount="1000000",
            on_behalf_of=326,
            token="not-an-address",
        )

    with pytest.raises(
        ValueError, match="destination must be a valid EVM address"
    ):
        await service.withdraw(
            amount="1000000",
            on_behalf_of=326,
            destination="not-an-address",
        )

    http_client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_server_wallet_rejects_invalid_on_behalf_of_before_network():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.get_hmac_credentials = Mock(
        return_value={"token_id": "token-1", "secret": "secret-1"}
    )
    http_client.post = AsyncMock()

    service = ServerWalletService(http_client)

    with pytest.raises(ValueError, match="on_behalf_of must be a positive integer"):
        await service.redeem_positions(
            condition_id=VALID_CONDITION_ID,
            on_behalf_of=0,
        )

    http_client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_server_wallet_rejects_legacy_api_key_only_auth():
    http_client = Mock()
    http_client.require_auth = Mock()
    http_client.get_hmac_credentials = Mock(return_value=None)
    http_client.post = AsyncMock()

    service = ServerWalletService(http_client)

    with pytest.raises(
        ValueError,
        match=(
            "Server wallet redeem/withdraw require HMAC-scoped API token auth; "
            "legacy API keys are not supported."
        ),
    ):
        await service.redeem_positions(
            condition_id=VALID_CONDITION_ID,
            on_behalf_of=326,
        )

    http_client.post.assert_not_awaited()
