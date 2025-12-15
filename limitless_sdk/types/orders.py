"""Order-related type definitions."""

from enum import Enum, IntEnum
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


class Side(IntEnum):
    """Order side enumeration.

    Attributes:
        BUY: Buy order (0)
        SELL: Sell order (1)
    """

    BUY = 0
    SELL = 1


class OrderType(Enum):
    """Order type enumeration.

    Attributes:
        GTC: Good Till Cancelled
        FOK: Fill Or Kill
        LIMIT: Limit order
        MARKET: Market order
    """

    GTC = "GTC"
    FOK = "FOK"
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class SignatureType(IntEnum):
    """Signature type enumeration.

    Attributes:
        EOA: Externally Owned Account (0)
        POLY_GNOSIS_SAFE: Polygon Gnosis Safe (1)
        POLY_PROXY: Polygon Proxy (2)
    """

    EOA = 0
    POLY_GNOSIS_SAFE = 1
    POLY_PROXY = 2


class MarketType(Enum):
    """Market type enumeration for contract addressing.

    Attributes:
        CLOB: Central Limit Order Book
        NEGRISK: Negative Risk market
    """

    CLOB = "CLOB"
    NEGRISK = "NEGRISK"


class UnsignedOrder(BaseModel):
    """Unsigned order structure.

    Attributes:
        salt: Random salt for order uniqueness
        maker: Maker address
        signer: Signer address
        taker: Taker address (0x0 for open orders)
        token_id: Token ID for the outcome
        maker_amount: Maker amount (scaled by 1e6)
        taker_amount: Taker amount (scaled by 1e6)
        expiration: Expiration timestamp (0 for no expiration)
        nonce: Order nonce
        fee_rate_bps: Fee rate in basis points
        side: Order side (0=BUY, 1=SELL)
        signature_type: Signature type (0=EOA, 1=POLY_GNOSIS_SAFE, 2=POLY_PROXY)
        price: Order price (optional, required for GTC orders, NOT part of EIP-712 signature)
    """

    salt: int
    maker: str
    signer: str
    taker: str
    token_id: str = Field(alias="tokenId")
    maker_amount: int = Field(alias="makerAmount")
    taker_amount: int = Field(alias="takerAmount")
    expiration: Optional[int] = None  # Optional for API response, int for EIP-712 signing, str for API submission
    nonce: int
    fee_rate_bps: int = Field(alias="feeRateBps")
    side: int
    signature_type: int = Field(alias="signatureType")
    price: Optional[float] = None  # Required for GTC orders, NOT part of EIP-712 signature

    model_config = ConfigDict(populate_by_name=True)


class SignedOrder(UnsignedOrder):
    """Signed order structure.

    Inherits all attributes from UnsignedOrder and adds:

    Attributes:
        signature: EIP-712 signature
        id: Order ID from API (optional, only present in responses)
        status: Order status from API (optional, only present in responses)
        size: Order size in USDC (optional, only present in responses)
        created_at: Order creation timestamp (optional, only present in responses)
        updated_at: Order update timestamp (optional, only present in responses)
    """

    signature: str
    id: Optional[str] = None
    status: Optional[str] = None
    size: Optional[float] = None
    created_at: Optional[str] = Field(None, alias="createdAt")
    updated_at: Optional[str] = Field(None, alias="updatedAt")

    def model_dump(self, **kwargs):
        """Custom serializer to convert expiration to string for API compatibility."""
        # Exclude None values by default
        kwargs.setdefault('exclude_none', True)
        data = super().model_dump(**kwargs)
        # Convert expiration to string for API compatibility
        if 'expiration' in data:
            data['expiration'] = str(data['expiration'])
        return data


class CreateOrderDto(BaseModel):
    """DTO for creating orders.

    Attributes:
        order: Signed order object
        owner_id: Owner ID (from user profile)
        order_type: Order type (GTC, FOK, etc.)
        market_slug: Market slug identifier
    """

    order: SignedOrder
    owner_id: int = Field(alias="ownerId")
    order_type: str = Field(alias="orderType")
    market_slug: str = Field(alias="marketSlug")

    model_config = ConfigDict(populate_by_name=True)

    def model_dump(self, **kwargs):
        """Custom serializer to ensure order field is properly serialized."""
        data = super().model_dump(**kwargs)
        # Ensure the nested order is serialized with expiration as string
        if 'order' in data and isinstance(self.order, SignedOrder):
            data['order'] = self.order.model_dump(**kwargs)
        return data


class CancelOrderDto(BaseModel):
    """DTO for canceling orders.

    Attributes:
        order_id: Order ID to cancel
    """

    order_id: str


class DeleteOrderBatchDto(BaseModel):
    """DTO for batch deleting orders.

    Attributes:
        order_ids: List of order IDs to cancel
    """

    order_ids: List[str] = Field(alias="orderIds")

    model_config = ConfigDict(populate_by_name=True)


class MarketSlugValidator(BaseModel):
    """Validator for market slugs.

    Attributes:
        slug: Market slug
    """

    slug: str


class OrderSigningConfig(BaseModel):
    """Configuration for EIP-712 order signing.

    Attributes:
        chain_id: Chain ID (8453 for Base mainnet, 84532 for Base testnet)
        contract_address: Verifying contract address
        market_type: Market type (CLOB or NEGRISK)

    Example:
        >>> config = OrderSigningConfig(
        ...     chain_id=8453,
        ...     contract_address="0xa4409D988CA2218d956BeEFD3874100F444f0DC3",
        ...     market_type=MarketType.CLOB
        ... )
    """

    chain_id: int
    contract_address: str
    market_type: MarketType


class OrderArgs(BaseModel):
    """Arguments for building an order.

    Attributes:
        token_id: Token ID for the outcome
        price: Price per share (0-1 range)
        size: Size in USDC
        side: Order side (BUY or SELL)
        expiration: Optional expiration timestamp
        taker: Optional taker address

    Example:
        >>> from limitless_sdk.types import OrderArgs, Side
        >>> args = OrderArgs(
        ...     token_id="123456",
        ...     price=0.65,
        ...     size=100.0,
        ...     side=Side.BUY
        ... )
    """

    token_id: str
    price: float
    size: float
    side: Side
    expiration: Optional[int] = None
    taker: Optional[str] = None


class MakerMatch(BaseModel):
    """Maker match information for filled orders.

    Attributes:
        id: Match ID
        created_at: Match creation timestamp
        matched_size: Size that was matched
        order_id: Order ID that was matched
    """

    id: str
    created_at: str = Field(alias="createdAt")
    matched_size: str = Field(alias="matchedSize")
    order_id: str = Field(alias="orderId")

    model_config = ConfigDict(populate_by_name=True)


class OrderResponse(BaseModel):
    """Order response from API.

    Attributes:
        order: Order details
        maker_matches: List of maker matches (for FOK or partial GTC fills)
    """

    order: SignedOrder
    maker_matches: Optional[List[MakerMatch]] = Field(None, alias="makerMatches")

    model_config = ConfigDict(populate_by_name=True)
