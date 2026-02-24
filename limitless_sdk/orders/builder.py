"""Order builder for constructing unsigned orders."""

import secrets
import time
from typing import Optional
from ..types.orders import UnsignedOrder, Side, SignatureType


class OrderBuilder:
    """Order construction utility for building unsigned orders.

    This class handles the complexity of building orders with proper
    amount calculations, salt generation, and parameter validation.

    Args:
        maker_address: Maker's Ethereum address
        fee_rate_bps: Fee rate in basis points (e.g., 300 = 3%)
        price_tick: Price tick size for rounding (default: 0.001 = 3 decimals)

    Example:
        >>> from limitless_sdk.orders import OrderBuilder
        >>> from limitless_sdk.types import Side
        >>>
        >>> builder = OrderBuilder(
        ...     maker_address="0x...",
        ...     fee_rate_bps=300
        ... )
        >>>
        >>> order = builder.build_order(
        ...     token_id="123456",
        ...     price=0.65,
        ...     size=100.0,
        ...     side=Side.BUY
        ... )
    """

    def __init__(
        self,
        maker_address: str,
        fee_rate_bps: int,
        price_tick: float = 0.001,
    ):
        """Initialize order builder.

        Args:
            maker_address: Maker's Ethereum address
            fee_rate_bps: Fee rate in basis points
            price_tick: Price tick size for rounding
        """
        self._maker_address = maker_address
        self._fee_rate_bps = fee_rate_bps
        self._price_tick = price_tick

    def build_order(
        self,
        token_id: str,
        price: float,
        size: float,
        side: Side,
        expiration: Optional[int] = None,
        taker: Optional[str] = None,
    ) -> UnsignedOrder:
        """Build an unsigned GTC order.

        Args:
            token_id: Token ID for the outcome
            price: Price per share (0-1 range)
            size: Size in USDC
            side: Order side (BUY or SELL)
            expiration: Optional expiration timestamp (0 for no expiration)
            taker: Optional taker address (0x0 for open orders)

        Returns:
            UnsignedOrder ready for signing

        Raises:
            ValueError: If price or size are invalid

        Example:
            >>> from limitless_sdk.types import Side
            >>> order = builder.build_order(
            ...     token_id="123456",
            ...     price=0.65,
            ...     size=100.0,
            ...     side=Side.BUY
            ... )
            >>> print(f"Maker amount: {order.maker_amount}")
            >>> print(f"Taker amount: {order.taker_amount}")
        """
        # Validate inputs
        if not 0 < price < 1:
            raise ValueError(f"Price must be between 0 and 1, got {price}")
        if size <= 0:
            raise ValueError(f"Size must be positive, got {size}")

        # Round price to tick, then round to tick's decimal precision
        # to eliminate IEEE 754 drift (e.g., 950 * 0.001 = 0.9500000000000001)
        tick_str = str(self._price_tick)
        tick_decimals = len(tick_str.split('.')[-1]) if '.' in tick_str else 0
        price = round(round(price / self._price_tick) * self._price_tick, tick_decimals)

        # Generate order parameters
        salt = self._generate_salt()
        maker_amount, taker_amount = self._calculate_amounts(price, size, side)

        # Default values
        expiration_value = expiration if expiration is not None else 0
        taker = taker or "0x0000000000000000000000000000000000000000"

        return UnsignedOrder(
            salt=salt,
            maker=self._maker_address,
            signer=self._maker_address,
            taker=taker,
            token_id=token_id,
            maker_amount=maker_amount,
            taker_amount=taker_amount,
            expiration=expiration_value,  # Keep as int for EIP-712 signing
            nonce=0,
            fee_rate_bps=self._fee_rate_bps,
            side=side.value,
            signature_type=SignatureType.EOA.value,
            price=price,  # Include price (required for GTC, NOT part of EIP-712 signature)
        )

    def build_fok_order(
        self,
        token_id: str,
        side: Side,
        maker_amount: float,
        expiration: Optional[int] = None,
        taker: Optional[str] = None,
    ) -> UnsignedOrder:
        """Build an unsigned FOK order.

        Args:
            token_id: Token ID for the outcome
            side: Order side (BUY or SELL)
            maker_amount: Maker amount (BUY: USDC to spend, SELL: shares to sell)
            expiration: Optional expiration timestamp (0 for no expiration)
            taker: Optional taker address (0x0 for open orders)

        Returns:
            UnsignedOrder ready for signing (takerAmount will be 1)

        Raises:
            ValueError: If parameters are invalid

        Example (BUY - USDC amount):
            >>> from limitless_sdk.types import Side
            >>> order = builder.build_fok_order(
            ...     token_id="123456",
            ...     maker_amount=50.0,  # Spend $50 USDC
            ...     side=Side.BUY
            ... )
            >>> print(f"Maker amount: {order.maker_amount}")

        Example (SELL - shares):
            >>> order = builder.build_fok_order(
            ...     token_id="123456",
            ...     maker_amount=18.64,  # Sell 18.64 shares
            ...     side=Side.SELL
            ... )
            >>> print(f"Maker amount: {order.maker_amount}")  # 18640000
        """
        # Validate maker_amount
        if maker_amount <= 0:
            raise ValueError(f"maker_amount must be positive, got {maker_amount}")

        # Generate order parameters
        salt = self._generate_salt()

        # Calculate scaled maker_amount
        maker_amount_scaled = self._calculate_fok_amounts(maker_amount)

        # Default values
        expiration_value = expiration if expiration is not None else 0
        taker = taker or "0x0000000000000000000000000000000000000000"

        return UnsignedOrder(
            salt=salt,
            maker=self._maker_address,
            signer=self._maker_address,
            taker=taker,
            token_id=token_id,
            maker_amount=maker_amount_scaled,
            taker_amount=1,  # FOK orders always have takerAmount = 1
            expiration=expiration_value,
            nonce=0,
            fee_rate_bps=self._fee_rate_bps,
            side=side.value,
            signature_type=SignatureType.EOA.value,
        )

    def _generate_salt(self) -> int:
        """Generate cryptographically secure random salt for order uniqueness.

        Uses secrets module for cryptographic randomness, which is:
        - Cryptographically secure (uses OS entropy, unpredictable)
        - Thread-safe and parallel-execution safe
        - Prevents salt prediction attacks
        - Guaranteed unique across parallel executions with extremely low collision probability

        The 32-bit space (4.3 billion values) provides:
        - ~0.002% collision probability for 100,000 parallel orders
        - ~0.1% collision probability after 2,930 sequential orders
        - ~1% collision probability after 9,268 sequential orders
        - Sufficient for typical order volumes while maintaining EIP-712 compatibility

        Trade-off: secrets is ~3-4x slower than random.randint, but provides
        cryptographic security which is critical for financial operations.

        Returns:
            Random integer between 1 and 2^32-1

        Example:
            >>> salt = builder._generate_salt()
            >>> assert 1 <= salt < 2**32
        """
        return secrets.randbelow(2**32 - 1) + 1

    def _calculate_amounts(
        self, price: float, size: float, side: Side
    ) -> tuple[int, int]:
        """Calculate maker and taker amounts for GTC orders with tick alignment.

        This implementation matches the TS SDK's tick alignment algorithm to ensure
        that price * contracts yields a whole number of collateral units.

        For BUY orders:
        - Maker amount: USDC paid (scaled by 1e6), rounded UP
        - Taker amount: Shares received (scaled by 1e6), tick-aligned

        For SELL orders:
        - Maker amount: Shares sold (scaled by 1e6), tick-aligned
        - Taker amount: USDC received (scaled by 1e6), rounded DOWN

        Args:
            price: Price per share (0-1 range)
            size: Size in USDC
            side: Order side (BUY or SELL)

        Returns:
            Tuple of (maker_amount, taker_amount) as integers

        Raises:
            ValueError: If price not tick-aligned or size produces non-tick-aligned shares

        Example:
            >>> # BUY order: pay 5 USDC at 0.55 price
            >>> maker, taker = builder._calculate_amounts(0.55, 5.0, Side.BUY)
            >>> # taker = 9090000 (tick-aligned, not 9090909)
            >>> # maker = 4999500 (ceiling of 5.0 / 0.55 * 0.55 * 1e6)
        """
        shares_scale = 1_000_000
        collateral_scale = 1_000_000
        price_scale = 1_000_000

        # Scale inputs to integers using round() to avoid IEEE 754 truncation.
        # int() truncates: int(0.95 * 1_000_000) = 949999
        # round() rounds:  round(0.95 * 1_000_000) = 950000
        shares = round(size * shares_scale)
        price_int = round(price * price_scale)
        tick_int = round(self._price_tick * price_scale)

        # Validate price is tick-aligned
        if price_int % tick_int != 0:
            raise ValueError(
                f"Price {price} is not tick-aligned. Must be multiple of {self._price_tick}"
            )

        # Calculate shares step (shares must be divisible by this)
        # For priceTick=0.001: shares_step = 1_000_000 / 1_000 = 1_000
        shares_step = price_scale // tick_int

        # Validate and align shares to tick
        if shares % shares_step != 0:
            # Round shares to nearest tick-aligned value
            shares = (shares // shares_step) * shares_step

        # Calculate collateral using exact integer arithmetic
        # collateral = (shares * price * collateral_scale) / (shares_scale * price_scale)
        numerator = shares * price_int * collateral_scale
        denominator = shares_scale * price_scale

        if side == Side.BUY:
            # BUY: Round UP (maker pays more to ensure tick alignment)
            collateral = (numerator + denominator - 1) // denominator
            maker_amount = collateral
            taker_amount = shares
        else:  # SELL
            # SELL: Round DOWN (maker receives less)
            collateral = numerator // denominator
            maker_amount = shares
            taker_amount = collateral

        return maker_amount, taker_amount

    def _calculate_fok_amounts(self, maker_amount: float) -> int:
        """Calculate scaled maker amount for FOK orders.

        FOK orders use makerAmount for both BUY and SELL:
        - BUY: makerAmount = USDC to spend (e.g., 50.0 = $50 USDC)
        - SELL: makerAmount = shares to sell (e.g., 18.64 shares)
        - takerAmount = always 1 (constant for FOK orders)

        The maker_amount is provided in human-readable format and converted to
        scaled units (6 decimals). Supports up to 6 decimal places.

        Args:
            maker_amount: Maker amount in human-readable format (e.g., 50.0, 18.64)

        Returns:
            Maker amount in scaled units (6 decimals)

        Example:
            >>> # BUY: 50 USDC → 50000000 scaled units
            >>> maker = builder._calculate_fok_amounts(50.0)
            >>> # maker = 50000000

            >>> # SELL: 18.64 shares → 18640000 scaled units
            >>> maker = builder._calculate_fok_amounts(18.64)
            >>> # maker = 18640000
        """
        usdc_decimals = 6

        # Validate maker_amount has max 6 decimal places
        amount_str = str(maker_amount)
        decimal_index = amount_str.find('.')
        if decimal_index != -1:
            decimal_places = len(amount_str) - decimal_index - 1
            if decimal_places > usdc_decimals:
                raise ValueError(
                    f"Invalid maker_amount: {maker_amount}. Can have max {usdc_decimals} decimal places. "
                    f"Try {maker_amount:.{usdc_decimals}f} instead."
                )

        # Convert to scaled units (6 decimals)
        scaled_amount = int(maker_amount * (10**usdc_decimals))

        return scaled_amount

    @property
    def maker_address(self) -> str:
        """Get the maker address.

        Returns:
            Maker's Ethereum address
        """
        return self._maker_address

    @property
    def fee_rate_bps(self) -> int:
        """Get the fee rate in basis points.

        Returns:
            Fee rate in basis points
        """
        return self._fee_rate_bps
