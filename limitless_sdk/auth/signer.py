"""Message signing for authentication."""

from typing import Dict
from eth_account import Account
from eth_account.messages import encode_defunct


class MessageSigner:
    """Message signing utility for authentication.

    This class handles message signing for authentication flows,
    creating the necessary headers for API authentication.

    Args:
        account: eth_account Account instance

    Example:
        >>> from eth_account import Account
        >>> from limitless_sdk.auth import MessageSigner
        >>>
        >>> account = Account.from_key(private_key)
        >>> signer = MessageSigner(account)
        >>> headers = await signer.create_auth_headers(signing_message)
    """

    def __init__(self, account: Account):
        """Initialize message signer.

        Args:
            account: Ethereum account for signing
        """
        self._account = account

    async def create_auth_headers(self, signing_message: str) -> Dict[str, str]:
        """Create authentication headers with signature.

        Args:
            signing_message: Message to sign from API

        Returns:
            Dictionary of authentication headers

        Example:
            >>> headers = await signer.create_auth_headers("Sign this message")
            >>> # Returns:
            >>> # {
            >>> #     "x-account": "0x...",
            >>> #     "x-signature": "0x...",
            >>> #     "x-signing-message": "0x..."
            >>> # }
        """
        # Sign the message
        signature = self.sign_message(signing_message)

        # Hex-encode the signing message for header
        # This prevents header injection issues with newlines
        hex_message = "0x" + signing_message.encode("utf-8").hex()

        # Ensure signature has 0x prefix for BytesLike format
        if not signature.startswith("0x"):
            signature = "0x" + signature

        return {
            "x-account": self._account.address,
            "x-signature": signature,
            "x-signing-message": hex_message,
        }

    def sign_message(self, message: str) -> str:
        """Sign a message using the private key.

        Args:
            message: Message to sign

        Returns:
            Signature as hex string

        Example:
            >>> signature = signer.sign_message("Hello World")
            >>> # Returns: "0x..."
        """
        message_hash = encode_defunct(text=message)
        signed_message = self._account.sign_message(message_hash)
        return signed_message.signature.hex()

    @property
    def address(self) -> str:
        """Get the signer's Ethereum address.

        Returns:
            Ethereum address
        """
        return self._account.address
