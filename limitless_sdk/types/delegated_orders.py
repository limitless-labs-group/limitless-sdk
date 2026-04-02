"""Delegated-order request and response types."""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class DelegatedOrderSubmission(BaseModel):
    """Unsigned order submission payload for delegated signing flows."""

    salt: int
    maker: str
    signer: str
    taker: str
    token_id: str = Field(alias="tokenId")
    maker_amount: int = Field(alias="makerAmount")
    taker_amount: int = Field(alias="takerAmount")
    expiration: str
    nonce: int
    fee_rate_bps: int = Field(alias="feeRateBps")
    side: int
    signature_type: int = Field(alias="signatureType")
    price: Optional[float] = None

    model_config = ConfigDict(populate_by_name=True)


class CreateDelegatedOrderRequest(BaseModel):
    """POST /orders payload for delegated-create flows."""

    order: DelegatedOrderSubmission
    order_type: str = Field(alias="orderType")
    market_slug: str = Field(alias="marketSlug")
    owner_id: int = Field(alias="ownerId")
    on_behalf_of: Optional[int] = Field(None, alias="onBehalfOf")

    model_config = ConfigDict(populate_by_name=True)


class CancelResponse(BaseModel):
    """Cancel endpoint response."""

    message: str
