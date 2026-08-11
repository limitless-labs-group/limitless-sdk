"""Partner self-service API-token service."""

from typing import List, Optional, Union
from urllib.parse import quote

from ..api.http_client import HttpClient, HttpRawResponse
from ..types.api_tokens import (
    ApiToken,
    DeriveApiTokenInput,
    DeriveApiTokenResponse,
    PartnerCapabilities,
)
from ..types.logger import ILogger, NoOpLogger


class ApiTokenService:
    """Partner self-service API-token operations."""

    def __init__(self, http_client: HttpClient, logger: Optional[ILogger] = None):
        self._http_client = http_client
        self._logger = logger or NoOpLogger()

    async def get_capabilities(
        self, identity_token: str, with_raw_response: bool = False
    ) -> Union[PartnerCapabilities, HttpRawResponse]:
        if not identity_token:
            raise ValueError("identity_token is required for get_capabilities")

        if with_raw_response:
            return await self._http_client.get_raw_with_identity(
                "/auth/api-tokens/capabilities",
                identity_token,
            )
        response = await self._http_client.get_with_identity(
            "/auth/api-tokens/capabilities",
            identity_token,
        )
        return PartnerCapabilities(**response)

    async def derive_token(
        self,
        identity_token: str,
        payload: DeriveApiTokenInput,
        with_raw_response: bool = False,
    ) -> Union[DeriveApiTokenResponse, HttpRawResponse]:
        if not identity_token:
            raise ValueError("identity_token is required for derive_token")

        self._logger.debug(
            "Deriving API token",
            {"label": payload.label, "scopes": payload.scopes},
        )
        body = payload.model_dump(by_alias=True, exclude_none=True)
        if with_raw_response:
            return await self._http_client.post_raw_with_identity(
                "/auth/api-tokens/derive",
                identity_token,
                body,
            )
        response = await self._http_client.post_with_identity(
            "/auth/api-tokens/derive",
            identity_token,
            body,
        )
        return DeriveApiTokenResponse(**response)

    async def list_tokens(
        self, with_raw_response: bool = False
    ) -> Union[List[ApiToken], HttpRawResponse]:
        self._http_client.require_auth("list_tokens")
        if with_raw_response:
            return await self._http_client.get_raw("/auth/api-tokens")
        response = await self._http_client.get("/auth/api-tokens")
        return [ApiToken(**item) for item in response]

    async def revoke_token(
        self, token_id: str, with_raw_response: bool = False
    ) -> Union[str, HttpRawResponse]:
        self._http_client.require_auth("revoke_token")
        path = f"/auth/api-tokens/{quote(token_id, safe='')}"
        if with_raw_response:
            return await self._http_client.delete_raw(path)
        response = await self._http_client.delete(path)
        return response["message"]
