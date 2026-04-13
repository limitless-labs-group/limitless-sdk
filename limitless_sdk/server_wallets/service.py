"""Server-managed wallet service."""

import re
from typing import Optional

from eth_utils import is_address

from ..api.http_client import HttpClient
from ..types.logger import ILogger, NoOpLogger
from ..types.server_wallets import (
    RedeemServerWalletInput,
    RedeemServerWalletResponse,
    WithdrawServerWalletInput,
    WithdrawServerWalletResponse,
)


_CONDITION_ID_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")
_INTEGER_STRING_RE = re.compile(r"^[0-9]+$")
_HMAC_ONLY_ERROR = (
    "Server wallet redeem/withdraw require HMAC-scoped API token auth; "
    "legacy API keys are not supported."
)


class ServerWalletService:
    """Server-managed wallet operations for delegated-signing partner flows."""

    def __init__(self, http_client: HttpClient, logger: Optional[ILogger] = None):
        self._http_client = http_client
        self._logger = logger or NoOpLogger()

    async def redeem_positions(
        self,
        condition_id: str,
        on_behalf_of: int,
    ) -> RedeemServerWalletResponse:
        self._require_hmac_auth("redeem_server_wallet_positions")
        self._validate_condition_id(condition_id)
        self._validate_on_behalf_of(on_behalf_of)

        payload = RedeemServerWalletInput(
            condition_id=condition_id,
            on_behalf_of=on_behalf_of,
        )

        self._logger.debug(
            "Redeeming server-wallet positions",
            {
                "condition_id": condition_id,
                "on_behalf_of": on_behalf_of,
            },
        )

        response = await self._http_client.post(
            "/portfolio/redeem",
            payload.model_dump(by_alias=True, exclude_none=True),
        )
        return RedeemServerWalletResponse(**response)

    async def withdraw(
        self,
        amount: str,
        on_behalf_of: int,
        token: Optional[str] = None,
        destination: Optional[str] = None,
    ) -> WithdrawServerWalletResponse:
        self._require_hmac_auth("withdraw_server_wallet_funds")
        self._validate_amount(amount)
        self._validate_on_behalf_of(on_behalf_of)

        if token is not None:
            self._validate_address(token, "token")
        if destination is not None:
            self._validate_address(destination, "destination")

        payload = WithdrawServerWalletInput(
            amount=amount,
            on_behalf_of=on_behalf_of,
            token=token,
            destination=destination,
        )

        self._logger.debug(
            "Withdrawing from server wallet",
            {
                "amount": amount,
                "on_behalf_of": on_behalf_of,
                "token": token,
                "destination": destination,
            },
        )

        response = await self._http_client.post(
            "/portfolio/withdraw",
            payload.model_dump(by_alias=True, exclude_none=True),
        )
        return WithdrawServerWalletResponse(**response)

    def _require_hmac_auth(self, operation: str) -> None:
        self._http_client.require_auth(operation)
        if self._http_client.get_hmac_credentials() is None:
            raise ValueError(_HMAC_ONLY_ERROR)

    def _validate_condition_id(self, condition_id: str) -> None:
        if not isinstance(condition_id, str) or not _CONDITION_ID_RE.fullmatch(
            condition_id
        ):
            raise ValueError(
                "condition_id must be a 0x-prefixed 32-byte hex string"
            )

    def _validate_on_behalf_of(self, on_behalf_of: int) -> None:
        if not isinstance(on_behalf_of, int) or on_behalf_of <= 0:
            raise ValueError("on_behalf_of must be a positive integer")

    def _validate_amount(self, amount: str) -> None:
        if (
            not isinstance(amount, str)
            or not _INTEGER_STRING_RE.fullmatch(amount)
            or int(amount) <= 0
        ):
            raise ValueError(
                "amount must be a positive integer string in the token smallest unit"
            )

    def _validate_address(self, value: str, field_name: str) -> None:
        if not isinstance(value, str) or not is_address(value):
            raise ValueError(f"{field_name} must be a valid EVM address")
