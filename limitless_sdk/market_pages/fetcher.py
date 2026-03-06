"""Market-pages and property-keys fetcher for Limitless Exchange."""

from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import parse_qs, urlencode, urlparse

from ..api.http_client import HttpClient
from ..types.logger import ILogger, NoOpLogger
from ..types.markets import Market
from ..types.market_pages import (
    MarketPage,
    MarketPageMarketsCursorResponse,
    MarketPageMarketsOffsetResponse,
    MarketPageMarketsParams,
    MarketPageMarketsResponse,
    NavigationNode,
    PropertyKey,
    PropertyOption,
)


MAX_REDIRECT_DEPTH = 3


class MarketPageFetcher:
    """Fetcher for market-pages and property-keys APIs."""

    def __init__(self, http_client: HttpClient, logger: Optional[ILogger] = None):
        self._http_client = http_client
        self._logger = logger or NoOpLogger()

    async def get_navigation(self) -> List[NavigationNode]:
        """Get navigation tree."""
        self._logger.debug("Fetching navigation tree")
        response_data = await self._http_client.get("/navigation")
        return [NavigationNode.model_validate(item) for item in response_data]

    async def get_market_page_by_path(self, path: str) -> MarketPage:
        """Resolve market page by path with manual 301 redirect handling."""
        return await self._get_market_page_by_path_internal(path, depth=0)

    async def _get_market_page_by_path_internal(self, path: str, depth: int) -> MarketPage:
        self._logger.debug("Resolving market page by path", {"path": path, "depth": depth})

        response = await self._http_client.get_raw(
            "/market-pages/by-path",
            params={"path": path},
            allow_redirects=False,
            accepted_statuses={200, 301},
        )

        if response.status == 200:
            return MarketPage.model_validate(response.data)

        if response.status != 301:
            raise RuntimeError(f"Unexpected response status: {response.status}")

        if depth >= MAX_REDIRECT_DEPTH:
            raise RuntimeError(
                f"Too many redirects while resolving market page path '{path}' (max {MAX_REDIRECT_DEPTH})"
            )

        location = response.headers.get("location")
        if not location:
            raise RuntimeError("Redirect response missing valid Location header")

        redirected_path = self._extract_redirect_path(location)
        self._logger.info(
            "Following market page redirect",
            {
                "from": path,
                "to": redirected_path,
                "depth": depth + 1,
            },
        )
        return await self._get_market_page_by_path_internal(redirected_path, depth + 1)

    def _extract_redirect_path(self, location: str) -> str:
        direct_by_path_prefix = "/market-pages/by-path"

        if location.startswith(direct_by_path_prefix):
            parsed = urlparse(location)
            path_values = parse_qs(parsed.query).get("path", [])
            if not path_values or not path_values[0]:
                raise RuntimeError(
                    "Redirect location '/market-pages/by-path' is missing required 'path' query parameter"
                )
            return path_values[0]

        if location.lower().startswith(("http://", "https://")):
            parsed = urlparse(location)
            if parsed.path == direct_by_path_prefix:
                path_values = parse_qs(parsed.query).get("path", [])
                if not path_values or not path_values[0]:
                    raise RuntimeError(
                        "Redirect location '/market-pages/by-path' is missing required 'path' query parameter"
                    )
                return path_values[0]
            return parsed.path or "/"

        return location

    async def get_markets(
        self,
        page_id: str,
        params: Optional[Union[MarketPageMarketsParams, Dict[str, Any]]] = None,
    ) -> MarketPageMarketsResponse:
        """Get markets for a market page with optional filtering and pagination."""
        if params is None:
            parsed_params = MarketPageMarketsParams()
        elif isinstance(params, MarketPageMarketsParams):
            parsed_params = params
        else:
            parsed_params = MarketPageMarketsParams.model_validate(params)

        if parsed_params.cursor is not None and parsed_params.page is not None:
            raise ValueError("Parameters `cursor` and `page` are mutually exclusive")

        query_parts: List[Tuple[str, str]] = []

        if parsed_params.page is not None:
            query_parts.append(("page", str(parsed_params.page)))
        if parsed_params.limit is not None:
            query_parts.append(("limit", str(parsed_params.limit)))
        if parsed_params.sort is not None:
            query_parts.append(("sort", parsed_params.sort))
        if parsed_params.cursor is not None:
            query_parts.append(("cursor", parsed_params.cursor))

        if parsed_params.filters:
            for key, value in parsed_params.filters.items():
                if isinstance(value, list):
                    query_parts.extend((key, self._stringify_filter_value(item)) for item in value)
                else:
                    query_parts.append((key, self._stringify_filter_value(value)))

        query_string = urlencode(query_parts, doseq=True)
        endpoint = f"/market-pages/{page_id}/markets"
        if query_string:
            endpoint = f"{endpoint}?{query_string}"

        self._logger.debug("Fetching market-page markets", {"page_id": page_id, "params": parsed_params.model_dump()})
        response_data = await self._http_client.get(endpoint)

        raw_markets = response_data.get("data", [])
        markets: List[Market] = []
        for item in raw_markets:
            market = Market.model_validate(item)
            market._http_client = self._http_client
            markets.append(market)

        if "pagination" in response_data:
            return MarketPageMarketsOffsetResponse(data=markets, pagination=response_data["pagination"])

        if "cursor" in response_data:
            return MarketPageMarketsCursorResponse(data=markets, cursor=response_data["cursor"])

        raise RuntimeError("Invalid market-page response: expected `pagination` or `cursor` metadata")

    async def get_property_keys(self) -> List[PropertyKey]:
        """List all property keys with options."""
        response_data = await self._http_client.get("/property-keys")
        return [PropertyKey.model_validate(item) for item in response_data]

    async def get_property_key(self, key_id: str) -> PropertyKey:
        """Get a single property key by ID."""
        response_data = await self._http_client.get(f"/property-keys/{key_id}")
        return PropertyKey.model_validate(response_data)

    async def get_property_options(self, key_id: str, parent_id: Optional[str] = None) -> List[PropertyOption]:
        """List options for a property key, optionally filtered by parent option ID."""
        endpoint = f"/property-keys/{key_id}/options"
        if parent_id:
            query = urlencode({"parentId": parent_id})
            endpoint = f"{endpoint}?{query}"

        response_data = await self._http_client.get(endpoint)
        return [PropertyOption.model_validate(item) for item in response_data]

    @staticmethod
    def _stringify_filter_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)
