"""Order-related type definitions."""

from enum import Enum, IntEnum
from decimal import Decimal, InvalidOperation
import math
import re
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


_INTEGER_STRING_RE = re.compile(r"^[+-]?\d+$")
_IEEE754_SAFE_INTEGER_MAX = 2**53 - 1


def _parse_integer_like(value: object) -> int:
    """Parse integer-like API values (int/float-integer/numeric-string) strictly."""
    if isinstance(value, bool):
        raise ValueError("value must be an integer or numeric string")

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if (
            math.isfinite(value)
            and value.is_integer()
            and abs(value) <= _IEEE754_SAFE_INTEGER_MAX
        ):
            return int(value)
        raise ValueError(
            "value must be a finite integer within IEEE-754 safe range"
        )

    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value cannot be an empty string")
        if not _INTEGER_STRING_RE.fullmatch(trimmed):
            raise ValueError(f"invalid integer string: {value!r}")
        return int(trimmed)

    raise ValueError("value must be an integer or numeric string")


def _parse_number_like(value: object) -> Optional[float]:
    """Parse number-like API values (number/numeric-string), preserving None."""
    if value is None:
        return None

    if isinstance(value, bool):
        raise ValueError("value must be a finite number or numeric string")

    if isinstance(value, int):
        try:
            number = float(value)
        except OverflowError as exc:
            raise ValueError("value is out of float range") from exc
    elif isinstance(value, float):
        number = value
    elif isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value cannot be an empty string")
        try:
            parsed_decimal = Decimal(trimmed)
        except InvalidOperation as exc:
            raise ValueError(f"invalid numeric string: {value!r}") from exc

        if not parsed_decimal.is_finite():
            raise ValueError("value must be finite")

        if (
            parsed_decimal == parsed_decimal.to_integral_value()
            and abs(int(parsed_decimal)) > _IEEE754_SAFE_INTEGER_MAX
        ):
            raise ValueError(
                "integer-like numeric string exceeds IEEE-754 safe integer range"
            )

        number = float(parsed_decimal)
    else:
        raise ValueError("value must be a finite number or numeric string")

    if not math.isfinite(number):
        raise ValueError("value must be finite")

    return number


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
        FAK: Fill And Kill (limit-like; unmatched remainder is killed)
        LIMIT: Limit order
        MARKET: Market order
    """

    GTC = "GTC"
    FOK = "FOK"
    FAK = "FAK"
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

    @field_validator("salt", "maker_amount", "taker_amount", mode="before")
    @classmethod
    def _parse_integer_payload_fields(cls, value: object) -> int:
        return _parse_integer_like(value)

    @field_validator("price", mode="before")
    @classmethod
    def _parse_price_payload_field(cls, value: object) -> Optional[float]:
        return _parse_number_like(value)


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
        post_only: Optional. When true, rejects the order if it would immediately match.
            Supported only for GTC orders. Defaults to false when omitted.
        stp_policy: Optional self-trade-prevention policy. Omit to use the server
            default ("cancel_maker").
    """

    order: SignedOrder
    owner_id: int = Field(alias="ownerId")
    order_type: str = Field(alias="orderType")
    market_slug: str = Field(alias="marketSlug")
    post_only: Optional[bool] = Field(None, alias="postOnly")
    stp_policy: Optional[str] = Field(None, alias="stpPolicy")

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
        contract_address: Verifying contract address (from venue.exchange)

    Example:
        >>> config = OrderSigningConfig(
        ...     chain_id=8453,
        ...     contract_address="0xa4409D988CA2218d956BeEFD3874100F444f0DC3"
        ... )
    """

    chain_id: int
    contract_address: str


class OrderArgs(BaseModel):
    """Arguments for building an order.

    Attributes:
        token_id: Token ID for the outcome
        price: Price per share (0-1 range)
        size: Size in USDC
        side: Order side (BUY or SELL)
        expiration: Optional expiration timestamp
        taker: Optional taker address
        post_only: Optional. When true, rejects the order if it would immediately match.
            Supported only for GTC orders. Defaults to false when omitted.
        stp_policy: Optional self-trade-prevention policy. Omit to use the server
            default ("cancel_maker").

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
    post_only: Optional[bool] = None
    stp_policy: Optional[str] = None


class MakerMatch(BaseModel):
    """Maker match information for filled orders.

    Attributes:
        id: Match ID
        created_at: Match creation timestamp
        matched_size: Size that was matched
        order_id: Order ID that was matched
    """

    id: str
    created_at: Optional[str] = Field(None, alias="createdAt")
    matched_size: Optional[str] = Field(None, alias="matchedSize")
    order_id: Optional[str] = Field(None, alias="orderId")

    model_config = ConfigDict(populate_by_name=True)


class OrderExecutionTotalsRaw(BaseModel):
    """Raw decimal totals for an order execution.

    All six fields are decimal STRINGS as sent by the API. They are not coerced
    to numbers so callers keep full precision.

    Attributes:
        contracts_gross: Gross contracts matched
        contracts_fee: Contracts taken as fee
        contracts_net: Net contracts after fee
        usd_gross: Gross USD value matched
        usd_fee: USD taken as fee
        usd_net: Net USD value after fee
    """

    contracts_gross: str = Field(alias="contractsGross")
    contracts_fee: str = Field(alias="contractsFee")
    contracts_net: str = Field(alias="contractsNet")
    usd_gross: str = Field(alias="usdGross")
    usd_fee: str = Field(alias="usdFee")
    usd_net: str = Field(alias="usdNet")

    model_config = ConfigDict(populate_by_name=True)


class OrderExecution(BaseModel):
    """Execution outcome reported alongside an order response.

    Always present on the create-order response. Carries the settlement state plus
    the self-trade-prevention signal: the taker STP reject surfaces here as a
    ``reason`` (HTTP-only; example value "STP_TAKER_REJECTED"), and any maker orders
    cancelled by STP are listed in ``stp_maker_cancels``.

    Type note: ``fee_rate_bps`` and ``effective_fee_bps`` are NUMBERS; ``totals_raw``
    fields and ``stp_maker_cancels`` entries are STRINGS. They are not coerced.

    Attributes:
        matched: Whether the order matched any liquidity
        settlement_status: Plain settlement-state string (e.g. "MATCHED", "UNMATCHED",
            "CANCELED", "DELAYED", "MINED", "CONFIRMED", "RETRYING", "FAILED"). No enum.
        trade_event_id: Trade event UUID when present
        tx_hash: Settlement transaction hash when present (may be null)
        client_order_id: Client order id echo when present
        eligible_at: ISO datetime the order becomes eligible (DELAYED only)
        reason: STP / rejection signal string (e.g. "STP_TAKER_REJECTED")
        stp_maker_cancels: UUIDs of maker orders cancelled by STP (set only when non-empty)
        fee_rate_bps: Configured fee rate in basis points
        effective_fee_bps: Effective fee rate applied in basis points
        totals_raw: Raw decimal totals for the execution
    """

    matched: bool
    settlement_status: str = Field(alias="settlementStatus")
    trade_event_id: Optional[str] = Field(None, alias="tradeEventId")
    tx_hash: Optional[str] = Field(None, alias="txHash")
    client_order_id: Optional[str] = Field(None, alias="clientOrderId")
    eligible_at: Optional[str] = Field(None, alias="eligibleAt")
    reason: Optional[str] = None
    stp_maker_cancels: Optional[List[str]] = Field(None, alias="stpMakerCancels")
    fee_rate_bps: int = Field(alias="feeRateBps")
    effective_fee_bps: int = Field(alias="effectiveFeeBps")
    totals_raw: OrderExecutionTotalsRaw = Field(alias="totalsRaw")

    model_config = ConfigDict(populate_by_name=True)


class OrderResponse(BaseModel):
    """Order response from API.

    Attributes:
        order: Order details
        maker_matches: List of maker matches (for FOK or partial GTC fills)
        execution: Execution outcome (settlement state, fees, totals, STP signals).
            Always present from a current API; Optional for fixture/back-compat.
    """

    order: SignedOrder
    maker_matches: Optional[List[MakerMatch]] = Field(None, alias="makerMatches")
    execution: Optional[OrderExecution] = None

    model_config = ConfigDict(populate_by_name=True)
