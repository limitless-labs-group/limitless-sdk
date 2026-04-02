"""Partner-account creation types."""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class CreatePartnerAccountInput(BaseModel):
    """Partner-owned profile creation payload."""

    display_name: Optional[str] = Field(None, alias="displayName")
    create_server_wallet: Optional[bool] = Field(None, alias="createServerWallet")

    model_config = ConfigDict(populate_by_name=True)


class CreatePartnerAccountEOAHeaders(BaseModel):
    """EOA verification headers for partner-account creation."""

    account: str
    signing_message: str = Field(alias="signingMessage")
    signature: str

    model_config = ConfigDict(populate_by_name=True)


class PartnerAccountResponse(BaseModel):
    """Partner-account creation response."""

    profile_id: int = Field(alias="profileId")
    account: str

    model_config = ConfigDict(populate_by_name=True)
