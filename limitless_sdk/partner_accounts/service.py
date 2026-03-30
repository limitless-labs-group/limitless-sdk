"""Partner-account creation service."""

from typing import Optional

from ..api.http_client import HttpClient
from ..types.logger import ILogger, NoOpLogger
from ..types.partner_accounts import (
    CreatePartnerAccountEOAHeaders,
    CreatePartnerAccountInput,
    PartnerAccountResponse,
)


class PartnerAccountService:
    """Partner-owned profile creation API."""

    DISPLAY_NAME_MAX_LENGTH = 44

    def __init__(self, http_client: HttpClient, logger: Optional[ILogger] = None):
        self._http_client = http_client
        self._logger = logger or NoOpLogger()

    async def create_account(
        self,
        payload: CreatePartnerAccountInput,
        eoa_headers: Optional[CreatePartnerAccountEOAHeaders] = None,
    ) -> PartnerAccountResponse:
        self._http_client.require_auth("create_partner_account")

        if (
            payload.display_name
            and len(payload.display_name) > self.DISPLAY_NAME_MAX_LENGTH
        ):
            raise ValueError(
                f"display_name must be at most {self.DISPLAY_NAME_MAX_LENGTH} characters"
            )

        server_wallet_mode = payload.create_server_wallet is True
        if not server_wallet_mode and eoa_headers is None:
            raise ValueError(
                "eoa_headers are required when create_server_wallet is not true"
            )

        headers = None
        if eoa_headers is not None:
            headers = {
                "x-account": eoa_headers.account,
                "x-signing-message": eoa_headers.signing_message,
                "x-signature": eoa_headers.signature,
            }

        self._logger.debug(
            "Creating partner account",
            {
                "display_name": payload.display_name,
                "create_server_wallet": payload.create_server_wallet,
            },
        )

        response = await self._http_client.post_with_headers(
            "/profiles/partner-accounts",
            payload.model_dump(by_alias=True, exclude_none=True),
            headers=headers,
        )
        return PartnerAccountResponse(**response)
