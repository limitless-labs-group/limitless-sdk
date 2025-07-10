"""Data models for Limitless Exchange SDK."""

from enum import Enum, IntEnum
from typing import List, Optional
from pydantic import BaseModel


class OrderSide(IntEnum):
    """Order side enumeration."""
    BUY = 0
    SELL = 1


class OrderType(str, Enum):
    """Order type enumeration."""
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class SignatureType(IntEnum):
    """Signature type enumeration."""
    EOA = 0
    POLY_GNOSIS_SAFE = 1
    POLY_PROXY = 2


class Order(BaseModel):
    """Order model for creating orders."""
    salt: int
    maker: str
    signer: str
    taker: str = "0x0000000000000000000000000000000000000000"
    tokenId: str
    makerAmount: str
    takerAmount: str
    expiration: int = 0
    nonce: int = 0
    price: str
    feeRateBps: int = 30
    side: OrderSide
    signature: str
    signatureType: SignatureType = SignatureType.EOA


class CreateOrderDto(BaseModel):
    """DTO for creating orders."""
    order: Order
    ownerId: Optional[int] = None
    orderType: OrderType = OrderType.LIMIT
    marketSlug: str


class CancelOrderDto(BaseModel):
    """DTO for canceling orders."""
    orderId: str


class DeleteOrderBatchDto(BaseModel):
    """DTO for batch deleting orders."""
    orderIds: List[str]


class MarketSlugValidator(BaseModel):
    """Validator for market slugs."""
    slug: str 