"""HTTP client for Limitless Exchange API."""

import json
import os
import platform
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Dict, Optional, Set, Tuple
from urllib.parse import urlencode

import aiohttp

from .errors import (
    APIError,
    AuthenticationError,
    ConflictError,
    RateLimitError,
    ValidationError,
)
from .hmac import compute_hmac_signature
from ..types.api_tokens import HMACCredentials
from ..types.logger import ILogger, NoOpLogger


DEFAULT_API_URL = "https://api.limitless.exchange"
DEFAULT_TIMEOUT = 30
SDK_ID = "lmts-sdk-py"
_AUTH_OVERRIDE_HEADERS = {
    "authorization",
    "cookie",
    "identity",
    "lmts-api-key",
    "lmts-signature",
    "lmts-timestamp",
    "x-api-key",
}
_REDACTED_HEADERS = {
    "authorization",
    "cookie",
    "identity",
    "lmts-api-key",
    "lmts-signature",
    "lmts-timestamp",
    "x-api-key",
}


def _resolve_sdk_version() -> str:
    try:
        return version("limitless-sdk")
    except PackageNotFoundError:
        return "0.0.0"


def _build_sdk_tracking_headers() -> Dict[str, str]:
    sdk_version = _resolve_sdk_version()
    return {
        "user-agent": f"{SDK_ID}/{sdk_version} (python/{platform.python_version()})",
        "x-sdk-version": f"{SDK_ID}/{sdk_version}",
    }


def _build_iso_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _serialize_json_body(data: Optional[Any]) -> str:
    if data is None:
        return ""
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


@dataclass
class HttpRawResponse:
    """Raw HTTP response with metadata."""

    status: int
    headers: Dict[str, str]
    data: Any


class HttpClient:
    """HTTP client wrapper for Limitless Exchange API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        hmac_credentials: Optional[HMACCredentials] = None,
        timeout: int = DEFAULT_TIMEOUT,
        additional_headers: Optional[Dict[str, str]] = None,
        logger: Optional[ILogger] = None,
    ):
        self.base_url = (
            base_url or os.getenv("LIMITLESS_API_URL") or DEFAULT_API_URL
        ).rstrip("/")
        self._api_key = api_key or os.getenv("LIMITLESS_API_KEY")
        self._hmac_credentials = (
            hmac_credentials.model_copy()
            if isinstance(hmac_credentials, HMACCredentials)
            else (
                HMACCredentials(**hmac_credentials)
                if isinstance(hmac_credentials, dict)
                else None
            )
        )
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._additional_headers = additional_headers or {}
        self._logger = logger or NoOpLogger()
        if not self._api_key and not self._hmac_credentials and not self._has_configured_header_auth():
            self._logger.warn(
                "No configured authentication found. Authenticated endpoints will fail. "
                "Set LIMITLESS_API_KEY, pass api_key, configure hmac_credentials, or supply auth headers."
            )
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _ensure_session(self) -> None:
        if self._session is None or self._session.closed:
            headers = {
                **_build_sdk_tracking_headers(),
                "Accept": "application/json",
            }
            self._session = aiohttp.ClientSession(headers=headers, timeout=self._timeout)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def get_logger(self) -> ILogger:
        return self._logger

    def get_api_key(self) -> Optional[str]:
        return self._api_key

    def get_hmac_credentials(self) -> Optional[HMACCredentials]:
        if not self._hmac_credentials:
            return None
        return self._hmac_credentials.model_copy()

    def set_api_key(self, api_key: str) -> None:
        self._api_key = api_key
        self._logger.debug("API key updated")

    def clear_api_key(self) -> None:
        self._api_key = None
        self._logger.debug("API key cleared")

    def set_hmac_credentials(self, hmac_credentials: HMACCredentials) -> None:
        self._hmac_credentials = hmac_credentials.model_copy()
        self._logger.debug("HMAC credentials updated")

    def clear_hmac_credentials(self) -> None:
        self._hmac_credentials = None
        self._logger.debug("HMAC credentials cleared")

    def require_auth(self, operation: str) -> None:
        if self._api_key or self._hmac_credentials or self._has_configured_header_auth():
            return
        raise ValueError(
            f"Authentication is required for {operation}; pass api_key, hmac_credentials, "
            "or configure auth headers."
        )

    def _has_configured_header_auth(self) -> bool:
        return any(
            key.lower() in _AUTH_OVERRIDE_HEADERS
            for key in self._additional_headers.keys()
        )

    def _build_url(self, path: str, params: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        request_path = path
        if params:
            request_path = f"{path}?{urlencode(params, doseq=True)}"
        return f"{self.base_url}{request_path}", request_path

    def _prepare_headers(
        self,
        method: str,
        request_path: str,
        body: str = "",
        additional_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        headers: Dict[str, str] = {}

        if self._additional_headers:
            headers.update(self._additional_headers)
        if additional_headers:
            headers.update(additional_headers)

        if not any(key.lower() in _AUTH_OVERRIDE_HEADERS for key in headers.keys()):
            if self._hmac_credentials:
                timestamp = _build_iso_timestamp()
                signature = compute_hmac_signature(
                    self._hmac_credentials.secret,
                    timestamp,
                    method,
                    request_path,
                    body,
                )
                headers["lmts-api-key"] = self._hmac_credentials.token_id
                headers["lmts-timestamp"] = timestamp
                headers["lmts-signature"] = signature
            elif self._api_key:
                headers["X-API-Key"] = self._api_key

        return headers

    def _sanitize_headers_for_logging(self, headers: Dict[str, str]) -> Dict[str, str]:
        sanitized: Dict[str, str] = {}
        for key, value in headers.items():
            if key.lower() in _REDACTED_HEADERS:
                sanitized[key] = "***"
            else:
                sanitized[key] = value
        return sanitized

    def _handle_error_response(
        self, status: int, data: Any, url: str, method: str
    ) -> APIError:
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
                "host": self.base_url,
                "status": status,
                "url": url,
                "method": method,
                "data": data,
            },
        )

        if status == 400:
            return ValidationError(message, status, data, url, method)
        if status == 409:
            return ConflictError(message, status, data, url, method)
        if status == 429:
            return RateLimitError(message, status, data, url, method)
        if status in (401, 403):
            return AuthenticationError(message, status, data, url, method)
        return APIError(message, status, data, url, method)

    async def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        await self._ensure_session()

        url, request_path = self._build_url(path, params)
        request_headers = self._prepare_headers("GET", request_path, "", headers)
        request_headers["Content-Type"] = "application/json"

        self._logger.debug(
            f"GET {path}",
            {
                "host": self.base_url,
                "full_url": url,
                "params": params,
                "headers": self._sanitize_headers_for_logging(request_headers),
            },
        )

        async with self._session.get(url, headers=request_headers) as response:
            try:
                data = await response.json()
            except aiohttp.ContentTypeError:
                data = await response.text()

            if response.status >= 400:
                raise self._handle_error_response(response.status, data, path, "GET")

            return data

    async def get_with_identity(
        self,
        path: str,
        identity_token: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if not identity_token:
            raise ValueError("identity_token is required")
        return await self.get(
            path,
            params=params,
            headers={"identity": f"Bearer {identity_token}"},
        )

    async def get_raw(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        allow_redirects: bool = True,
        accepted_statuses: Optional[Set[int]] = None,
    ) -> HttpRawResponse:
        await self._ensure_session()

        url, request_path = self._build_url(path, params)
        request_headers = self._prepare_headers("GET", request_path, "", headers)
        request_headers["Content-Type"] = "application/json"

        self._logger.debug(
            f"GET {path} (raw)",
            {
                "host": self.base_url,
                "full_url": url,
                "params": params,
                "allow_redirects": allow_redirects,
                "headers": self._sanitize_headers_for_logging(request_headers),
            },
        )

        async with self._session.get(
            url,
            headers=request_headers,
            allow_redirects=allow_redirects,
        ) as response:
            try:
                data = await response.json()
            except aiohttp.ContentTypeError:
                data = await response.text()

            headers_map = {str(k).lower(): str(v) for k, v in response.headers.items()}

            if response.status >= 400:
                raise self._handle_error_response(response.status, data, path, "GET")

            if accepted_statuses and response.status in accepted_statuses:
                return HttpRawResponse(status=response.status, headers=headers_map, data=data)

            return HttpRawResponse(status=response.status, headers=headers_map, data=data)

    async def post(
        self,
        path: str,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        await self._ensure_session()

        url, request_path = self._build_url(path)
        body = _serialize_json_body(data)
        request_headers = self._prepare_headers("POST", request_path, body, headers)
        request_headers["Content-Type"] = "application/json"

        self._logger.debug(
            f"POST {path}",
            {
                "host": self.base_url,
                "full_url": url,
                "has_data": data is not None,
                "headers": self._sanitize_headers_for_logging(request_headers),
            },
        )

        async with self._session.post(
            url,
            data=body or None,
            headers=request_headers,
        ) as response:
            try:
                response_data = await response.json()
            except aiohttp.ContentTypeError:
                response_data = await response.text()

            if response.status >= 400:
                raise self._handle_error_response(response.status, response_data, path, "POST")

            return response_data

    async def post_with_identity(
        self,
        path: str,
        identity_token: str,
        data: Optional[Any] = None,
    ) -> Any:
        if not identity_token:
            raise ValueError("identity_token is required")
        return await self.post(
            path,
            data=data,
            headers={"identity": f"Bearer {identity_token}"},
        )

    async def post_with_headers(
        self,
        path: str,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        return await self.post(path, data=data, headers=headers)

    async def post_with_response(
        self,
        path: str,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> aiohttp.ClientResponse:
        await self._ensure_session()

        url, request_path = self._build_url(path)
        body = _serialize_json_body(data)
        request_headers = self._prepare_headers("POST", request_path, body, headers)
        request_headers["Content-Type"] = "application/json"

        self._logger.debug(
            f"POST {path} (with response)",
            {
                "has_data": data is not None,
                "headers": self._sanitize_headers_for_logging(request_headers),
            },
        )

        response = await self._session.post(
            url,
            data=body or None,
            headers=request_headers,
        )

        if response.status >= 400:
            try:
                response_data = await response.json()
            except aiohttp.ContentTypeError:
                response_data = await response.text()

            raise self._handle_error_response(response.status, response_data, path, "POST")

        return response

    async def delete(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        await self._ensure_session()

        url, request_path = self._build_url(path, params)
        request_headers = self._prepare_headers("DELETE", request_path, "", headers)

        self._logger.debug(
            f"DELETE {path}",
            {
                "host": self.base_url,
                "full_url": url,
                "headers": self._sanitize_headers_for_logging(request_headers),
            },
        )

        async with self._session.delete(
            url,
            headers=request_headers,
            skip_auto_headers=["Content-Type"],
        ) as response:
            try:
                data = await response.json()
            except aiohttp.ContentTypeError:
                data = await response.text()

            if response.status >= 400:
                raise self._handle_error_response(response.status, data, path, "DELETE")

            return data
