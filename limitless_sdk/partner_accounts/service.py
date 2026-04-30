"""Partner-account creation service."""

from typing import Optional

from ..api.http_client import HttpClient
from ..types.logger import ILogger, NoOpLogger
from ..types.partner_accounts import (
    CreatePartnerAccountEOAHeaders,
    CreatePartnerAccountInput,
    PartnerAccountAllowanceResponse,
    PartnerAccountResponse,
)


_PARTNER_ACCOUNT_ALLOWANCE_HMAC_ONLY_ERROR = (
    "Partner account allowance recovery requires HMAC-scoped API token auth; "
    "legacy API keys are not supported."
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

    async def check_allowances(
        self,
        profile_id: int,
    ) -> PartnerAccountAllowanceResponse:
        """Check delegated-trading allowance readiness from live chain state."""

        self._require_allowance_hmac_auth("check_partner_account_allowances")
        path = self._partner_account_allowances_path(profile_id)

        self._logger.debug(
            "Checking partner-account allowances",
            {"profile_id": profile_id},
        )

        response = await self._http_client.get(path)
        return PartnerAccountAllowanceResponse(**response)

    async def retry_allowances(
        self,
        profile_id: int,
    ) -> PartnerAccountAllowanceResponse:
        """Retry delegated-trading allowances that remain missing after a live chain re-check.

        Submitted targets in the response mean this retry request submitted a
        sponsored transaction or user operation. Call ``check_allowances`` again
        after a short delay to observe confirmed chain state.
        """

        self._require_allowance_hmac_auth("retry_partner_account_allowances")
        path = self._partner_account_allowances_path(profile_id)

        self._logger.debug(
            "Retrying partner-account allowances",
            {"profile_id": profile_id},
        )

        response = await self._http_client.post(f"{path}/retry", {})
        return PartnerAccountAllowanceResponse(**response)

    def _require_allowance_hmac_auth(self, operation: str) -> None:
        self._http_client.require_auth(operation)
        if self._http_client.get_hmac_credentials() is None:
            raise ValueError(_PARTNER_ACCOUNT_ALLOWANCE_HMAC_ONLY_ERROR)

    def _partner_account_allowances_path(self, profile_id: int) -> str:
        if not isinstance(profile_id, int) or profile_id <= 0:
            raise ValueError("profile_id must be a positive integer")

        return f"/profiles/partner-accounts/{profile_id}/allowances"
