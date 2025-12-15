"""Order signer for EIP-712 signature generation."""

from typing import Dict, Any
from eth_account import Account
from eth_account.messages import encode_typed_data

from ..types.orders import UnsignedOrder, OrderSigningConfig
from ..types.logger import ILogger, NoOpLogger
from ..utils.constants import PROTOCOL_NAME, PROTOCOL_VERSION


class OrderSigner:
    """EIP-712 order signing utility.

    This class handles the complexity of EIP-712 typed data construction
    and signing for Limitless Exchange orders.

    Args:
        account: eth_account Account instance for signing
        logger: Optional logger for debugging

    Example:
        >>> from eth_account import Account
        >>> from limitless_sdk.orders import OrderSigner
        >>> from limitless_sdk.types import OrderSigningConfig, MarketType
        >>>
        >>> account = Account.from_key(private_key)
        >>> signer = OrderSigner(account)
        >>>
        >>> config = OrderSigningConfig(
        ...     chain_id=8453,
        ...     contract_address="0x...",
        ...     market_type=MarketType.CLOB
        ... )
        >>>
        >>> signature = await signer.sign_order(unsigned_order, config)
    """

    def __init__(self, account: Account, logger: ILogger = None):
        """Initialize order signer.

        Args:
            account: Ethereum account for signing
            logger: Optional logger for debugging
        """
        self._account = account
        self._logger = logger or NoOpLogger()

    async def sign_order(
        self, order: UnsignedOrder, config: OrderSigningConfig
    ) -> str:
        """Sign an order with EIP-712.

        This method constructs the EIP-712 typed data structure and signs it
        using the account's private key.

        Args:
            order: Unsigned order to sign
            config: Signing configuration (chain ID, contract address, market type)

        Returns:
            Signature as hex string with 0x prefix

        Example:
            >>> signature = await signer.sign_order(order, config)
            >>> # Returns: "0x..."
            >>> assert signature.startswith("0x")
            >>> assert len(signature) == 132  # 0x + 130 hex chars
        """
        self._logger.debug(
            "Signing order with EIP-712",
            {
                "chain_id": config.chain_id,
                "contract": config.contract_address,
                "market_type": config.market_type.value,
            },
        )

        # Build EIP-712 typed data
        typed_data = self._build_typed_data(order, config)

        # Sign using eth_account's EIP-712 implementation
        encoded_message = encode_typed_data(full_message=typed_data)
        signed_message = self._account.sign_message(encoded_message)

        # Extract signature with 0x prefix
        signature = signed_message.signature.hex()
        if not signature.startswith("0x"):
            signature = "0x" + signature

        self._logger.info(
            "Order signature generated",
            {
                "signature_preview": signature[:10] + "...",
                "chain_id": config.chain_id,
                "market_type": config.market_type.value,
            },
        )

        return signature

    def _build_typed_data(
        self, order: UnsignedOrder, config: OrderSigningConfig
    ) -> Dict[str, Any]:
        """Build EIP-712 typed data structure.

        Constructs the typed data structure following the EIP-712 standard:
        - Domain: Protocol name, version, chain ID, verifying contract
        - Types: Order struct definition
        - Message: Order data

        Args:
            order: Unsigned order
            config: Signing configuration

        Returns:
            Dictionary containing EIP-712 typed data structure

        Reference:
            EIP-712: https://eips.ethereum.org/EIPS/eip-712
        """
        # Domain separator
        domain = {
            "name": PROTOCOL_NAME,
            "version": PROTOCOL_VERSION,
            "chainId": config.chain_id,
            "verifyingContract": config.contract_address,
        }

        # Type definitions
        types = {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Order": [
                {"name": "salt", "type": "uint256"},
                {"name": "maker", "type": "address"},
                {"name": "signer", "type": "address"},
                {"name": "taker", "type": "address"},
                {"name": "tokenId", "type": "uint256"},
                {"name": "makerAmount", "type": "uint256"},
                {"name": "takerAmount", "type": "uint256"},
                {"name": "expiration", "type": "uint256"},
                {"name": "nonce", "type": "uint256"},
                {"name": "feeRateBps", "type": "uint256"},
                {"name": "side", "type": "uint8"},
                {"name": "signatureType", "type": "uint8"},
            ],
        }

        # Message data
        message = {
            "salt": order.salt,
            "maker": order.maker,
            "signer": order.signer,
            "taker": order.taker,
            "tokenId": int(order.token_id),
            "makerAmount": order.maker_amount,
            "takerAmount": order.taker_amount,
            "expiration": order.expiration,
            "nonce": order.nonce,
            "feeRateBps": order.fee_rate_bps,
            "side": order.side,
            "signatureType": order.signature_type,
        }

        # EIP-712 typed data structure
        typed_data = {
            "types": types,
            "primaryType": "Order",
            "domain": domain,
            "message": message,
        }

        return typed_data

    @property
    def address(self) -> str:
        """Get the signer's Ethereum address.

        Returns:
            Ethereum address
        """
        return self._account.address
