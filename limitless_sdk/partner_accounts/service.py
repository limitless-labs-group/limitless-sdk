"""Partner-account creation service."""

from typing import Any, Dict, Optional, Union
from urllib.parse import quote

from ..api.http_client import HttpClient
from ..types.logger import ILogger, NoOpLogger
from ..types.partner_accounts import (
    CreatePartnerAccountEOAHeaders,
    CreatePartnerAccountInput,
    ListPartnerAccountsParams,
    ListPartnerAccountsResponse,
    PartnerAccountAllowanceResponse,
    PartnerAccountResponse,
    PartnerWithdrawalAddressInput,
    PartnerWithdrawalAddressResponse,
)


_PARTNER_ACCOUNT_ALLOWANCE_HMAC_ONLY_ERROR = (
    "Partner account allowance recovery requires HMAC-scoped API token auth; "
    "legacy API keys are not supported."
)
_PARTNER_ACCOUNT_LIST_HMAC_ONLY_ERROR = (
    "Partner account listing requires HMAC-scoped API token auth; "
    "legacy API keys are not supported."
)
_PARTNER_ACCOUNTS_MAX_LIMIT = 25


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

    async def list_accounts(
        self,
        params: Optional[Union[ListPartnerAccountsParams, Dict[str, Any]]] = None,
    ) -> ListPartnerAccountsResponse:
        """List or recover partner-owned accounts created by the authenticated partner.

        Requires HMAC-scoped API-token auth with ``account_creation``. Optional
        params are ``account``, ``limit``, and ``page``; ``limit`` is capped to
        the API maximum of 25 before sending.
        """

        self._require_hmac_auth(
            "list_partner_accounts",
            _PARTNER_ACCOUNT_LIST_HMAC_ONLY_ERROR,
        )
        query_params = self._partner_accounts_query_params(params)

        self._logger.debug("Listing partner accounts", query_params)

        response = await self._http_client.get(
            "/profiles/partner-accounts",
            params=query_params or None,
        )
        return ListPartnerAccountsResponse(**response)

    async def check_allowances(
        self,
        profile_id: int,
    ) -> PartnerAccountAllowanceResponse:
        """Check delegated-trading allowance readiness from live chain state."""

        self._require_hmac_auth(
            "check_partner_account_allowances",
            _PARTNER_ACCOUNT_ALLOWANCE_HMAC_ONLY_ERROR,
        )
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

        self._require_hmac_auth(
            "retry_partner_account_allowances",
            _PARTNER_ACCOUNT_ALLOWANCE_HMAC_ONLY_ERROR,
        )
        path = self._partner_account_allowances_path(profile_id)

        self._logger.debug(
            "Retrying partner-account allowances",
            {"profile_id": profile_id},
        )

        response = await self._http_client.post(f"{path}/retry", {})
        return PartnerAccountAllowanceResponse(**response)

    async def add_withdrawal_address(
        self,
        identity_token: str,
        payload: PartnerWithdrawalAddressInput,
    ) -> PartnerWithdrawalAddressResponse:
        """Add an active partner withdrawal destination allowlist entry.

        This endpoint uses Privy identity-token auth. API-token auth is not used
        for withdrawal-address allowlist management.
        """

        if not identity_token:
            raise ValueError("identity_token is required for add_withdrawal_address")
        if not payload.address:
            raise ValueError("address is required for add_withdrawal_address")

        self._logger.debug(
            "Adding partner withdrawal address",
            {"address": payload.address},
        )

        response = await self._http_client.post_with_identity(
            "/portfolio/withdrawal-addresses",
            identity_token,
            payload.model_dump(by_alias=True, exclude_none=True),
        )
        return PartnerWithdrawalAddressResponse(**response)

    async def delete_withdrawal_address(
        self,
        identity_token: str,
        address: str,
    ) -> None:
        """Remove a partner withdrawal destination allowlist entry."""

        if not identity_token:
            raise ValueError("identity_token is required for delete_withdrawal_address")
        if not address:
            raise ValueError("address is required for delete_withdrawal_address")

        self._logger.debug(
            "Deleting partner withdrawal address",
            {"address": address},
        )

        await self._http_client.delete_with_identity(
            f"/portfolio/withdrawal-addresses/{quote(address, safe='')}",
            identity_token,
        )

    def _require_hmac_auth(self, operation: str, error_message: str) -> None:
        self._http_client.require_auth(operation)
        if self._http_client.get_hmac_credentials() is None:
            raise ValueError(error_message)

    def _partner_accounts_query_params(
        self,
        params: Optional[Union[ListPartnerAccountsParams, Dict[str, Any]]],
    ) -> Dict[str, Any]:
        if params is None:
            raw_params: Dict[str, Any] = {}
        elif isinstance(params, ListPartnerAccountsParams):
            raw_params = params.model_dump(exclude_none=True)
        elif isinstance(params, dict):
            raw_params = {
                key: value for key, value in params.items() if value is not None
            }
        else:
            raise ValueError("params must be a ListPartnerAccountsParams or dict")

        query: Dict[str, Any] = {}

        if "account" in raw_params:
            account = raw_params["account"]
            if not isinstance(account, str) or not account.strip():
                raise ValueError("account must be a non-empty string")
            query["account"] = account.strip()

        if "limit" in raw_params:
            query["limit"] = self._format_positive_integer(
                raw_params["limit"],
                "limit",
                _PARTNER_ACCOUNTS_MAX_LIMIT,
            )

        if "page" in raw_params:
            query["page"] = self._format_positive_integer(raw_params["page"], "page")

        return query

    def _partner_account_allowances_path(self, profile_id: int) -> str:
        if not isinstance(profile_id, int) or profile_id <= 0:
            raise ValueError("profile_id must be a positive integer")

        return f"/profiles/partner-accounts/{profile_id}/allowances"

    def _format_positive_integer(
        self,
        value: Any,
        name: str,
        max_value: Optional[int] = None,
    ) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")

        if max_value is not None:
            return min(value, max_value)
        return value
