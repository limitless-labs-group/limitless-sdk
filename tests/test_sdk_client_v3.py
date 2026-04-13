"""Tests for the modular root Client partner surface."""

from limitless_sdk import Client
from limitless_sdk.api_tokens import ApiTokenService
from limitless_sdk.delegated_orders import DelegatedOrderService
from limitless_sdk.partner_accounts import PartnerAccountService
from limitless_sdk.server_wallets import ServerWalletService
from limitless_sdk.types import HMACCredentials


def test_client_initializes_partner_services():
    client = Client(api_key="plain-api-key")

    assert isinstance(client.api_tokens, ApiTokenService)
    assert isinstance(client.partner_accounts, PartnerAccountService)
    assert isinstance(client.delegated_orders, DelegatedOrderService)
    assert isinstance(client.server_wallets, ServerWalletService)
    assert client.http.get_api_key() == "plain-api-key"


def test_new_websocket_client_reuses_hmac_credentials():
    client = Client(
        hmac_credentials=HMACCredentials(
            token_id="token-123",
            secret="c2VjcmV0",
        )
    )

    ws_client = client.new_websocket_client()

    assert ws_client._config.hmac_credentials is not None
    assert ws_client._config.hmac_credentials.token_id == "token-123"
