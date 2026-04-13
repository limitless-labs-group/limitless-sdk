"""API-token, HMAC, and partner capability types."""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


ScopeTrading = "trading"
ScopeAccountCreation = "account_creation"
ScopeDelegatedSigning = "delegated_signing"
ScopeWithdrawal = "withdrawal"


class HMACCredentials(BaseModel):
    """HMAC credentials for scoped API-token authentication."""

    token_id: str = Field(alias="tokenId")
    secret: str

    model_config = ConfigDict(populate_by_name=True)


class ApiTokenProfile(BaseModel):
    """Profile reference embedded in API-token responses."""

    id: int
    account: str


class DeriveApiTokenInput(BaseModel):
    """Self-service token derivation payload."""

    label: Optional[str] = None
    scopes: Optional[List[str]] = None


class DeriveApiTokenResponse(BaseModel):
    """One-time token derivation response."""

    api_key: str = Field(alias="apiKey")
    secret: str
    token_id: str = Field(alias="tokenId")
    created_at: str = Field(alias="createdAt")
    scopes: List[str]
    profile: ApiTokenProfile

    model_config = ConfigDict(populate_by_name=True)


class ApiToken(BaseModel):
    """Active API-token list item."""

    token_id: str = Field(alias="tokenId")
    label: Optional[str] = None
    scopes: List[str]
    created_at: str = Field(alias="createdAt")
    last_used_at: Optional[str] = Field(None, alias="lastUsedAt")

    model_config = ConfigDict(populate_by_name=True)


class PartnerCapabilities(BaseModel):
    """Partner self-service capability configuration."""

    partner_profile_id: int = Field(alias="partnerProfileId")
    token_management_enabled: bool = Field(alias="tokenManagementEnabled")
    allowed_scopes: List[str] = Field(alias="allowedScopes")

    model_config = ConfigDict(populate_by_name=True)
