"""HTTP client for Limitless Exchange API."""

import json
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import aiohttp

from .errors import APIError, AuthenticationError, RateLimitError
from ..types.logger import ILogger, NoOpLogger


DEFAULT_API_URL = "https://api.limitless.exchange"
DEFAULT_TIMEOUT = 30


class HttpClient:
    """HTTP client wrapper for Limitless Exchange API.

    This class provides a centralized HTTP client with cookie management,
    error handling, and request/response interceptors.

    Args:
        base_url: Base URL for API requests (default: https://api.limitless.exchange)
        timeout: Request timeout in seconds (default: 30)
        session_cookie: Session cookie for authenticated requests
        additional_headers: Additional headers to include in all requests
        logger: Optional logger for debugging (default: NoOpLogger)

    Example:
        >>> http_client = HttpClient()
        >>> data = await http_client.get("/markets")
    """

    def __init__(
        self,
        base_url: str = DEFAULT_API_URL,
        timeout: int = DEFAULT_TIMEOUT,
        session_cookie: Optional[str] = None,
        additional_headers: Optional[Dict[str, str]] = None,
        logger: Optional[ILogger] = None,
    ):
        """Initialize HTTP client."""
        self._base_url = base_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session_cookie = session_cookie
        self._additional_headers = additional_headers or {}
        self._logger = logger or NoOpLogger()
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()

    async def _ensure_session(self) -> None:
        """Ensure aiohttp session exists."""
        if self._session is None or self._session.closed:
            # Only set Accept header by default (not Content-Type) - as this was passed to delete and causing issues :)
            # Content-Type will be added per-request where needed
            # Note: additional_headers are added in _prepare_headers() per-request
            headers = {
                "Accept": "application/json",
            }

            cookie_jar = aiohttp.CookieJar()
            self._session = aiohttp.ClientSession(
                headers=headers, timeout=self._timeout, cookie_jar=cookie_jar
            )

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def set_session_cookie(self, cookie: str) -> None:
        """Set session cookie for authenticated requests.

        Args:
            cookie: Session cookie value
        """
        self._session_cookie = cookie

    def clear_session_cookie(self) -> None:
        """Clear the session cookie."""
        self._session_cookie = None

    def _prepare_headers(self, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Prepare request headers with session cookie.

        Args:
            additional_headers: Additional headers for this request

        Returns:
            Complete headers dict including global additional_headers
        """
        headers = {}

        # Add global headers from constructor
        if self._additional_headers:
            headers.update(self._additional_headers)

        # Add session cookie
        if self._session_cookie:
            headers["Cookie"] = f"limitless_session={self._session_cookie}"

        # Add per-request headers (can override global headers)
        if additional_headers:
            headers.update(additional_headers)

        return headers

    def _handle_error_response(
        self, status: int, data: Any, url: str, method: str
    ) -> APIError:
        """Transform error response into appropriate exception.

        Args:
            status: HTTP status code
            data: Response data
            url: Request URL
            method: HTTP method

        Returns:
            Appropriate APIError subclass
        """

        if isinstance(data, dict):
            if isinstance(data.get("message"), list):
                messages = []
                for err in data["message"]:
                    if isinstance(err, dict):
                        details = {k: v for k, v in err.items() if v}
                        messages.append(", ".join(f"{k}: {v}" for k, v in details.items()))
                    else:
                        messages.append(str(err))
                message = " | ".join(messages) or data.get("error", str(data))
            else:
           
                message = (
                    data.get("message")
                    or data.get("error")
                    or data.get("msg")
                    or json.dumps(data)
                )
        else:
            message = str(data)

        self._logger.debug(
            "Raw API Error Response",
            {
                "host": self._base_url,
                "status": status,
                "url": url,
                "method": method,
                "data": data
            },
        )

  
        if status == 429:
            return RateLimitError(message, status, data, url, method)
        elif status in (401, 403):
            return AuthenticationError(message, status, data, url, method)
        else:
            return APIError(message, status, data, url, method)

    async def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Perform GET request.

        Args:
            path: Request path (e.g., "/markets")
            params: Query parameters
            headers: Additional headers

        Returns:
            Response data

        Raises:
            APIError: If request fails
        """
        await self._ensure_session()

        url = f"{self._base_url}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"

        request_headers = self._prepare_headers(headers)
        request_headers["Content-Type"] = "application/json"

        self._logger.debug(
            f"GET {path}",
            {
                "host": self._base_url,
                "full_url": url,
                "params": params,
                "headers": {k: v for k, v in request_headers.items() if k.lower() != 'cookie'},  # Hide cookie for security
                "has_session_cookie": self._session_cookie is not None
            }
        )

        async with self._session.get(url, headers=request_headers) as response:
            try:
                data = await response.json()
            except aiohttp.ContentTypeError:
                # incase for some reson resp is not json
                data = await response.text()

            if response.status >= 400:
                error = self._handle_error_response(
                    response.status, data, path, "GET"
                )
                raise error

            return data

    async def post(
        self,
        path: str,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Perform POST request.

        Args:
            path: Request path
            data: Request body data
            headers: Additional headers

        Returns:
            Response data

        Raises:
            APIError: If request fails
        """
        await self._ensure_session()

        url = f"{self._base_url}{path}"
        request_headers = self._prepare_headers(headers)
        request_headers["Content-Type"] = "application/json"

        import time
        start_time = time.time()

        self._logger.debug(
            f"POST {path}",
            {
                "host": self._base_url,
                "full_url": url,
                "has_data": data is not None,
                "headers": {k: v for k, v in request_headers.items() if k.lower() != 'cookie'},  # excluding cookie for sec reasons
                "has_session_cookie": self._session_cookie is not None
            }
        )

        async with self._session.post(
            url, json=data, headers=request_headers
        ) as response:
            request_time = time.time() - start_time
            self._logger.info(
                f"POST {path} - HTTP request completed",
                {
                    "request_time_ms": round(request_time * 1000, 2),
                    "status": response.status
                }
            )
            try:
                response_data = await response.json()
            except aiohttp.ContentTypeError:
                response_data = await response.text()

            if response.status >= 400:
                error = self._handle_error_response(
                    response.status, response_data, path, "POST"
                )
                raise error

            return response_data

    async def post_with_response(
        self,
        path: str,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> aiohttp.ClientResponse:
        """Perform POST request and return full response.

        Useful when you need access to response headers (e.g., for cookie extraction).

        Args:
            path: Request path
            data: Request body data
            headers: Additional headers

        Returns:
            Full aiohttp ClientResponse object

        Raises:
            APIError: If request fails
        """
        await self._ensure_session()

        url = f"{self._base_url}{path}"
        request_headers = self._prepare_headers(headers)
        request_headers["Content-Type"] = "application/json"

        self._logger.debug(f"POST {path} (with response)", {"has_data": data is not None})

        response = await self._session.post(url, json=data, headers=request_headers)

        if response.status >= 400:
            try:
                response_data = await response.json()
            except aiohttp.ContentTypeError:
                response_data = await response.text()

            error = self._handle_error_response(
                response.status, response_data, path, "POST"
            )
            raise error

        return response

    async def delete(
        self,
        path: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Perform DELETE request.

        Args:
            path: Request path
            headers: Additional headers

        Returns:
            Response data

        Raises:
            APIError: If request fails
        """
        await self._ensure_session()

        url = f"{self._base_url}{path}"
        request_headers = self._prepare_headers(headers)

        self._logger.debug(f"DELETE {path}")

        async with self._session.delete(
            url,
            headers=request_headers,
            skip_auto_headers=['Content-Type']
        ) as response:
            try:
                data = await response.json()
            except aiohttp.ContentTypeError:
                data = await response.text()

            if response.status >= 400:
                error = self._handle_error_response(
                    response.status, data, path, "DELETE"
                )
                raise error

            return data

    def extract_cookies(self, response: aiohttp.ClientResponse) -> Dict[str, str]:
        """Extract cookies from response headers.

        Args:
            response: aiohttp response object

        Returns:
            Dictionary of cookie names to values
        """
        cookies: Dict[str, str] = {}
        set_cookie = response.headers.getall("Set-Cookie", [])

        for cookie_string in set_cookie:
            parts = cookie_string.split(";")[0].split("=", 1)
            if len(parts) == 2:
                cookies[parts[0].strip()] = parts[1].strip()

        return cookies
