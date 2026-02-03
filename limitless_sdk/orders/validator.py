"""Order validation utilities."""

import re
from typing import Optional
from ..types.orders import UnsignedOrder, SignedOrder, Side


class ValidationError(Exception):
    """Validation error class.

    Raised when order validation fails.

    Example:
        >>> try:
        ...     validate_order_args(order_args)
        ... except ValidationError as e:
        ...     print(f"Validation failed: {e}")
    """

    pass


def validate_gtc_order_args(
    token_id: str,
    price: float,
    size: float,
    side: Side,
    taker: Optional[str] = None,
    expiration: Optional[int] = None,
    nonce: Optional[int] = None,
) -> None:
    """Validate GTC order arguments before building.

    Args:
        token_id: Token ID for the outcome
        price: Price per share (0-1 range)
        size: Size in USDC
        side: Order side (BUY or SELL)
        taker: Optional taker address
        expiration: Optional expiration timestamp
        nonce: Optional nonce

    Raises:
        ValidationError: If validation fails

    Example:
        >>> from limitless_sdk.types import Side
        >>> validate_gtc_order_args(
        ...     token_id="123456",
        ...     price=0.65,
        ...     size=100.0,
        ...     side=Side.BUY
        ... )
    """
    # Validate tokenId
    if not token_id:
        raise ValidationError("TokenId is required")

    if token_id == "0":
        raise ValidationError("TokenId cannot be zero")

    # Validate tokenId format (should be numeric string)
    if not re.match(r"^\d+$", token_id):
        raise ValidationError(f"Invalid tokenId format: {token_id}")

    # Validate taker address if provided
    if taker is not None:
        if not _is_valid_address(taker):
            raise ValidationError(f"Invalid taker address: {taker}")

    # Validate expiration if provided
    if expiration is not None:
        if not isinstance(expiration, int) or expiration < 0:
            raise ValidationError(f"Invalid expiration format: {expiration}")

    # Validate nonce if provided
    if nonce is not None:
        if not isinstance(nonce, int) or nonce < 0:
            raise ValidationError(f"Invalid nonce: {nonce}")

    # GTC order validation
    if not isinstance(price, (int, float)):
        raise ValidationError("Price must be a valid number")

    if price < 0 or price > 1:
        raise ValidationError(f"Price must be between 0 and 1, got: {price}")

    if not isinstance(size, (int, float)):
        raise ValidationError("Size must be a valid number")

    if size <= 0:
        raise ValidationError(f"Size must be positive, got: {size}")


def validate_fok_order_args(
    token_id: str,
    maker_amount: float,
    side: Side,
    taker: Optional[str] = None,
    expiration: Optional[int] = None,
    nonce: Optional[int] = None,
) -> None:
    """Validate FOK order arguments before building.

    Args:
        token_id: Token ID for the outcome
        maker_amount: Maker amount (BUY: USDC to spend, SELL: shares to sell)
        side: Order side (BUY or SELL)
        taker: Optional taker address
        expiration: Optional expiration timestamp
        nonce: Optional nonce

    Raises:
        ValidationError: If validation fails

    Example:
        >>> from limitless_sdk.types import Side
        >>> validate_fok_order_args(
        ...     token_id="123456",
        ...     maker_amount=50.0,
        ...     side=Side.BUY
        ... )
    """
    # Validate tokenId
    if not token_id:
        raise ValidationError("TokenId is required")

    if token_id == "0":
        raise ValidationError("TokenId cannot be zero")

    # Validate tokenId format (should be numeric string)
    if not re.match(r"^\d+$", token_id):
        raise ValidationError(f"Invalid tokenId format: {token_id}")

    # Validate taker address if provided
    if taker is not None:
        if not _is_valid_address(taker):
            raise ValidationError(f"Invalid taker address: {taker}")

    # Validate expiration if provided
    if expiration is not None:
        if not isinstance(expiration, int) or expiration < 0:
            raise ValidationError(f"Invalid expiration format: {expiration}")

    # Validate nonce if provided
    if nonce is not None:
        if not isinstance(nonce, int) or nonce < 0:
            raise ValidationError(f"Invalid nonce: {nonce}")

    # FOK order validation
    if not isinstance(maker_amount, (int, float)):
        raise ValidationError("Amount must be a valid number")

    if maker_amount <= 0:
        raise ValidationError(f"Amount must be positive, got: {maker_amount}")

    # Validate max 2 decimal places
    amount_str = str(maker_amount)
    decimal_index = amount_str.find(".")
    if decimal_index != -1:
        decimal_places = len(amount_str) - decimal_index - 1
        if decimal_places > 2:
            raise ValidationError(
                f"Amount must have max 2 decimal places, got: {maker_amount} ({decimal_places} decimals)"
            )


def validate_unsigned_order(order: UnsignedOrder) -> None:
    """Validate an unsigned order.

    Args:
        order: Unsigned order to validate

    Raises:
        ValidationError: If validation fails

    Example:
        >>> validate_unsigned_order(unsigned_order)
    """
    # Validate addresses
    if not _is_valid_address(order.maker):
        raise ValidationError(f"Invalid maker address: {order.maker}")

    if not _is_valid_address(order.signer):
        raise ValidationError(f"Invalid signer address: {order.signer}")

    if not _is_valid_address(order.taker):
        raise ValidationError(f"Invalid taker address: {order.taker}")

    # Validate amounts
    if not order.maker_amount or order.maker_amount == 0:
        raise ValidationError("MakerAmount must be greater than zero")

    if not order.taker_amount or order.taker_amount == 0:
        raise ValidationError("TakerAmount must be greater than zero")

    # Validate amounts are positive numbers
    if not isinstance(order.maker_amount, int) or order.maker_amount <= 0:
        raise ValidationError(f"Invalid makerAmount: {order.maker_amount}")

    if not isinstance(order.taker_amount, int) or order.taker_amount <= 0:
        raise ValidationError(f"Invalid takerAmount: {order.taker_amount}")

    if not re.match(r"^\d+$", order.token_id):
        raise ValidationError(f"Invalid tokenId format: {order.token_id}")

    if not isinstance(order.expiration, int) or order.expiration < 0:
        raise ValidationError(f"Invalid expiration format: {order.expiration}")

    # Validate salt
    if not isinstance(order.salt, int) or order.salt <= 0:
        raise ValidationError(f"Invalid salt: {order.salt}")

    # Validate nonce
    if not isinstance(order.nonce, int) or order.nonce < 0:
        raise ValidationError(f"Invalid nonce: {order.nonce}")

    # Validate feeRateBps
    if not isinstance(order.fee_rate_bps, int) or order.fee_rate_bps < 0:
        raise ValidationError(f"Invalid feeRateBps: {order.fee_rate_bps}")

    # Validate side (0 or 1)
    if order.side not in (0, 1):
        raise ValidationError(
            f"Invalid side: {order.side}. Must be 0 (BUY) or 1 (SELL)"
        )

    # Validate signatureType
    if not isinstance(order.signature_type, int) or order.signature_type < 0:
        raise ValidationError(f"Invalid signatureType: {order.signature_type}")

    # Validate price if present (for GTC orders)
    if order.price is not None:
        if not isinstance(order.price, (int, float)):
            raise ValidationError("Price must be a valid number")

        if order.price < 0 or order.price > 1:
            raise ValidationError(f"Price must be between 0 and 1, got: {order.price}")


def validate_signed_order(order: SignedOrder) -> None:
    """Validate a signed order.

    Args:
        order: Signed order to validate

    Raises:
        ValidationError: If validation fails

    Example:
        >>> validate_signed_order(signed_order)
    """
    # Validate unsigned order fields first
    validate_unsigned_order(order)

    # Validate signature
    if not order.signature:
        raise ValidationError("Signature is required")

    if not order.signature.startswith("0x"):
        raise ValidationError("Signature must start with 0x")

    # Signature should be 132 characters (0x + 130 hex chars for 65 bytes)
    if len(order.signature) != 132:
        raise ValidationError(
            f"Invalid signature length: {len(order.signature)}. Expected 132 characters."
        )

    # Validate hex format
    if not re.match(r"^0x[0-9a-fA-F]{130}$", order.signature):
        raise ValidationError("Signature must be valid hex string")


def _is_valid_address(address: str) -> bool:
    """Check if address is a valid Ethereum address.

    Args:
        address: Ethereum address to validate

    Returns:
        True if valid, False otherwise
    """
    if not address or not isinstance(address, str):
        return False

    # Check basic format: 0x followed by 40 hex characters
    if not re.match(r"^0x[0-9a-fA-F]{40}$", address):
        return False

    return True
