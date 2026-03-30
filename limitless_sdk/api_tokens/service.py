"""Partner self-service API-token service."""

from typing import List, Optional
from urllib.parse import quote

from ..api.http_client import HttpClient
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

    async def get_capabilities(self, identity_token: str) -> PartnerCapabilities:
        if not identity_token:
            raise ValueError("identity_token is required for get_capabilities")

        response = await self._http_client.get_with_identity(
            "/auth/api-tokens/capabilities",
            identity_token,
        )
        return PartnerCapabilities(**response)

    async def derive_token(
        self,
        identity_token: str,
        payload: DeriveApiTokenInput,
    ) -> DeriveApiTokenResponse:
        if not identity_token:
            raise ValueError("identity_token is required for derive_token")

        self._logger.debug(
            "Deriving API token",
            {"label": payload.label, "scopes": payload.scopes},
        )
        response = await self._http_client.post_with_identity(
            "/auth/api-tokens/derive",
            identity_token,
            payload.model_dump(by_alias=True, exclude_none=True),
        )
        return DeriveApiTokenResponse(**response)

    async def list_tokens(self) -> List[ApiToken]:
        self._http_client.require_auth("list_tokens")
        response = await self._http_client.get("/auth/api-tokens")
        return [ApiToken(**item) for item in response]

    async def revoke_token(self, token_id: str) -> str:
        self._http_client.require_auth("revoke_token")
        response = await self._http_client.delete(
            f"/auth/api-tokens/{quote(token_id, safe='')}",
        )
        return response["message"]
