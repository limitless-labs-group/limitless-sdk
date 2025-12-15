"""Authenticator for Limitless Exchange API."""

from typing import Optional
from ..api.http_client import HttpClient
from ..api.errors import AuthenticationError
from .signer import MessageSigner
from ..types.auth import LoginOptions, UserProfile, AuthResult
from ..types.logger import ILogger, NoOpLogger


class Authenticator:
    """Authenticator for Limitless Exchange API.

    This class handles the complete authentication flow:
    1. Get signing message from API
    2. Sign message with wallet
    3. Login and obtain session cookie
    4. Verify authentication status

    Args:
        http_client: HTTP client for API requests
        signer: Message signer for wallet operations
        logger: Optional logger for debugging (default: NoOpLogger)

    Example:
        >>> from limitless_sdk.api import HttpClient
        >>> from limitless_sdk.auth import Authenticator, MessageSigner
        >>> from eth_account import Account
        >>>
        >>> account = Account.from_key(private_key)
        >>> http_client = HttpClient()
        >>> signer = MessageSigner(account)
        >>> authenticator = Authenticator(http_client, signer)
        >>>
        >>> # Authenticate
        >>> result = await authenticator.authenticate()
        >>> print(f"Session: {result.session_cookie}")
        >>> print(f"User ID: {result.profile.id}")
    """

    def __init__(
        self,
        http_client: HttpClient,
        signer: MessageSigner,
        logger: Optional[ILogger] = None,
    ):
        """Initialize authenticator.

        Args:
            http_client: HTTP client for API requests
            signer: Message signer for wallet operations
            logger: Optional logger for debugging
        """
        self._http_client = http_client
        self._signer = signer
        self._logger = logger or NoOpLogger()

    async def get_signing_message(self) -> str:
        """Get signing message from the API.

        Returns:
            Signing message string

        Raises:
            APIError: If API request fails

        Example:
            >>> message = await authenticator.get_signing_message()
            >>> print(message)
            "Sign this message to authenticate..."
        """
        self._logger.debug("Requesting signing message from API")

        message = await self._http_client.get("/auth/signing-message")

        self._logger.debug("Received signing message", {"length": len(message)})
        return message

    async def authenticate(self, options: Optional[LoginOptions] = None) -> AuthResult:
        """Authenticate with the API and obtain session cookie.

        Args:
            options: Login options (default: EOA client)

        Returns:
            Authentication result with session cookie and user profile

        Raises:
            ValueError: If smart wallet required but not provided
            AuthenticationError: If authentication fails
            APIError: If API request fails

        Example:
            >>> # EOA authentication
            >>> result = await authenticator.authenticate()
            >>>
            >>> # Etherspot authentication
            >>> result = await authenticator.authenticate(
            ...     LoginOptions(client="etherspot", smart_wallet="0x...")
            ... )
        """
        options = options or LoginOptions()
        client = options.client

        self._logger.info(
            "Starting authentication",
            {"client": client, "has_smart_wallet": options.smart_wallet is not None},
        )

        # Validate Etherspot requires smart wallet
        if client == "etherspot" and not options.smart_wallet:
            self._logger.error("Smart wallet address required for ETHERSPOT client")
            raise ValueError("Smart wallet address is required for ETHERSPOT client")

        try:
            signing_message = await self.get_signing_message()

            self._logger.debug("Creating signature headers")
            headers = await self._signer.create_auth_headers(signing_message)

            self._logger.debug("Sending authentication request", {"client": client})

            payload = {"client": client}
            if options.smart_wallet:
                payload["smartWallet"] = options.smart_wallet

            response = await self._http_client.post_with_response(
                "/auth/login", payload, headers=headers
            )
            self._logger.debug("Extracting session cookie from response")
            cookies = self._http_client.extract_cookies(response)

            session_cookie = cookies.get("limitless_session")
            if not session_cookie:
                self._logger.error("Session cookie not found in response headers")
                raise AuthenticationError("Failed to obtain session cookie from response")

            # Set cookie in HTTP client for future requests
            self._http_client.set_session_cookie(session_cookie)

            # Parse user profile from response body
            try:
                response_data = await response.json()
            except Exception:
                response_data = await response.text()
                raise AuthenticationError(
                    f"Failed to parse user profile from response: {response_data}"
                )

            profile = UserProfile(**response_data)

            self._logger.info(
                "Authentication successful",
                {"account": profile.account, "client": profile.client},
            )

            return AuthResult(session_cookie=session_cookie, profile=profile)

        except AuthenticationError:
            # Re-raise authentication errors
            raise
        except Exception as error:
            self._logger.error("Authentication failed", error, {"client": client})
            raise

    async def verify_auth(self, session_cookie: Optional[str] = None) -> str:
        """Verify the current authentication status.

        Args:
            session_cookie: Session cookie to verify (optional, uses current if not provided)

        Returns:
            User's Ethereum address

        Raises:
            AuthenticationError: If session is invalid
            APIError: If API request fails

        Example:
            >>> address = await authenticator.verify_auth(session_cookie)
            >>> print(f"Authenticated as: {address}")
        """
        self._logger.debug("Verifying authentication session")

        # Save current cookie
        original_cookie = self._http_client._session_cookie

        try:
            # Set cookie if provided
            if session_cookie:
                self._http_client.set_session_cookie(session_cookie)

            # Verify auth
            address = await self._http_client.get("/auth/verify-auth")

            self._logger.info("Session verified", {"address": address})
            return address

        except Exception as error:
            self._logger.error("Session verification failed", error)
            raise

        finally:
            # Restore original cookie
            if original_cookie:
                self._http_client.set_session_cookie(original_cookie)
            elif session_cookie:
                self._http_client.clear_session_cookie()

    async def logout(self, session_cookie: Optional[str] = None) -> None:
        """Log out and clear the session.

        Args:
            session_cookie: Session cookie to invalidate (optional, uses current if not provided)

        Raises:
            APIError: If logout request fails

        Example:
            >>> await authenticator.logout(session_cookie)
            >>> print("Logged out successfully")
        """
        self._logger.debug("Logging out session")

        # Save current cookie
        original_cookie = self._http_client._session_cookie

        try:
            # Set cookie if provided
            if session_cookie:
                self._http_client.set_session_cookie(session_cookie)

            # Logout
            await self._http_client.post("/auth/logout", {})

            self._logger.info("Logout successful")

        except Exception as error:
            self._logger.error("Logout failed", error)
            raise

        finally:
            # Restore original cookie
            if original_cookie:
                self._http_client.set_session_cookie(original_cookie)
            elif session_cookie:
                self._http_client.clear_session_cookie()
