"""Root OOP entrypoint for the modular SDK."""

from typing import Optional, Union

from eth_account import Account

from .api.http_client import DEFAULT_TIMEOUT, HttpClient
from .api_tokens import ApiTokenService
from .delegated_orders import DelegatedOrderService
from .market_pages import MarketPageFetcher
from .markets import MarketFetcher
from .orders import OrderClient
from .partner_accounts import PartnerAccountService
from .portfolio import PortfolioFetcher
from .types.api_tokens import HMACCredentials
from .types.logger import ILogger
from .websocket import WebSocketClient
from .websocket.types import WebSocketConfig


class Client:
    """Root OOP entrypoint for the SDK."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        hmac_credentials: Optional[HMACCredentials] = None,
        timeout: int = DEFAULT_TIMEOUT,
        additional_headers: Optional[dict] = None,
        logger: Optional[ILogger] = None,
    ):
        self.http = HttpClient(
            base_url=base_url,
            api_key=api_key,
            hmac_credentials=hmac_credentials,
            timeout=timeout,
            additional_headers=additional_headers,
            logger=logger,
        )

        shared_logger = self.http.get_logger()
        self.markets = MarketFetcher(self.http, shared_logger)
        self.market_pages = MarketPageFetcher(self.http, shared_logger)
        self.portfolio = PortfolioFetcher(self.http, shared_logger)
        self.api_tokens = ApiTokenService(self.http, shared_logger)
        self.partner_accounts = PartnerAccountService(self.http, shared_logger)
        self.delegated_orders = DelegatedOrderService(self.http, shared_logger)

    async def __aenter__(self):
        await self.http.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http.__aexit__(exc_type, exc_val, exc_tb)

    async def close(self) -> None:
        await self.http.close()

    @classmethod
    def from_http_client(cls, http_client: HttpClient) -> "Client":
        client = cls.__new__(cls)
        client.http = http_client
        shared_logger = http_client.get_logger()
        client.markets = MarketFetcher(http_client, shared_logger)
        client.market_pages = MarketPageFetcher(http_client, shared_logger)
        client.portfolio = PortfolioFetcher(http_client, shared_logger)
        client.api_tokens = ApiTokenService(http_client, shared_logger)
        client.partner_accounts = PartnerAccountService(http_client, shared_logger)
        client.delegated_orders = DelegatedOrderService(http_client, shared_logger)
        return client

    def new_order_client(self, wallet_or_private_key: Union[str, object]) -> OrderClient:
        wallet = (
            Account.from_key(wallet_or_private_key)
            if isinstance(wallet_or_private_key, str)
            else wallet_or_private_key
        )
        return OrderClient(
            http_client=self.http,
            wallet=wallet,
            market_fetcher=self.markets,
            logger=self.http.get_logger(),
        )

    def new_websocket_client(self, config: Optional[WebSocketConfig] = None) -> WebSocketClient:
        config = config or WebSocketConfig()
        if not config.api_key and self.http.get_api_key():
            config.api_key = self.http.get_api_key()
        if not config.hmac_credentials and self.http.get_hmac_credentials():
            config.hmac_credentials = self.http.get_hmac_credentials()
        return WebSocketClient(config=config, logger=self.http.get_logger())
