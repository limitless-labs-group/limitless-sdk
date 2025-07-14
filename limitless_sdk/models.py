"""Data models for Limitless Exchange SDK."""

from enum import Enum, IntEnum
from typing import List, Optional
from dataclasses import dataclass


class OrderSide(IntEnum):
    """Order side enumeration."""
    BUY = 0
    SELL = 1


class OrderType(Enum):
    """Order type enumeration."""
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    GTC = "GTC"


class SignatureType(IntEnum):
    """Signature type enumeration."""
    EOA = 0
    POLY_GNOSIS_SAFE = 1
    POLY_PROXY = 2


@dataclass
class Order:
    """Order model for creating orders."""
    salt: int
    maker: str
    signer: str
    tokenId: str
    makerAmount: int
    takerAmount: int
    feeRateBps: int
    side: int  # 0 - BUY, 1 - SELL
    signature: str
    signatureType: int  # 0, 1, 2, 3
    taker: Optional[str] = None
    expiration: Optional[str] = None
    nonce: Optional[int] = None
    price: Optional[float] = None


@dataclass
class CreateOrderDto:
    """DTO for creating orders."""
    order: Order
    ownerId: int
    orderType: str
    marketSlug: str


@dataclass
class CancelOrderDto:
    """DTO for canceling orders."""
    order_id: str


@dataclass
class DeleteOrderBatchDto:
    """DTO for batch deleting orders."""
    orderIds: List[str]


@dataclass
class MarketSlugValidator:
    """Validator for market slugs."""
    slug: str 