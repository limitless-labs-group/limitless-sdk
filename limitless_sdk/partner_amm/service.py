"""Partner AMM trading service.

Manages AMM market approvals and server-wallet buy/sell submissions. Validation
and workflow behavior are ported from the Go SDK (``limitless/amm.go``).
"""

import asyncio
import re
from typing import Any, Dict, Optional, Union

from ..api.http_client import HttpClient, HttpRawResponse
from ..types.logger import ILogger, NoOpLogger
from ..types.partner_amm import (
    AMM_SIDE_BUY,
    AMM_SIDE_SELL,
    AmmAllowanceParams,
    AmmAllowanceResponse,
    AmmBuyParams,
    AmmBuyResponse,
    AmmSellParams,
    AmmSellResponse,
)


_AMM_HMAC_ONLY_ERROR = (
    "AMM operations require HMAC-scoped API token auth or an explicit Privy "
    "identity token; legacy API keys are not supported."
)
_DEFAULT_ALLOWANCE_POLL_INTERVAL = 2.0
_DEFAULT_ALLOWANCE_MAX_ATTEMPTS = 30
_AMM_IDEMPOTENCY_KEY_MAX_LENGTH = 128
_AMM_MARKET_MAX_LENGTH = 255
_AMM_AMOUNT_MAX_LENGTH = 78
_AMM_MAX_ON_BEHALF_OF = 2147483647
_AMM_MAX_UINT256 = (1 << 256) - 1
_AMM_POSITIVE_INTEGER_RE = re.compile(r"^[1-9]\d*$")


class PartnerAmmService:
    """AMM market approval and buy/sell submission operations."""

    def __init__(self, http_client: HttpClient, logger: Optional[ILogger] = None):
        self._http_client = http_client
        self._logger = logger or NoOpLogger()

    async def check_allowance(
        self,
        params: AmmAllowanceParams,
        identity_token: Optional[str] = None,
        with_raw_response: bool = False,
    ) -> Union[AmmAllowanceResponse, HttpRawResponse]:
        """Read the live BUY or SELL approval state.

        ``current_allowance`` is present on BUY responses and omitted on SELL.
        """
        identity_token = self._prepare_auth("check_amm_allowance", identity_token)
        body = self._build_allowance_body(params)

        self._logger.debug(
            "Checking AMM allowance",
            {
                "market": body["market"],
                "side": body["side"],
                "onBehalfOf": body.get("onBehalfOf"),
            },
        )

        return await self._post(
            "/amm/allowances/check",
            body,
            identity_token,
            with_raw_response,
            AmmAllowanceResponse,
        )

    async def approve_allowance(
        self,
        params: AmmAllowanceParams,
        identity_token: Optional[str] = None,
        with_raw_response: bool = False,
    ) -> Union[AmmAllowanceResponse, HttpRawResponse]:
        """Submit a missing BUY or SELL approval.

        A submitted (202) response is not confirmation; poll
        :meth:`check_allowance` until ``confirmed`` is true.
        """
        identity_token = self._prepare_auth("approve_amm_allowance", identity_token)
        body = self._build_allowance_body(params)

        self._logger.debug(
            "Approving AMM allowance",
            {
                "market": body["market"],
                "side": body["side"],
                "onBehalfOf": body.get("onBehalfOf"),
            },
        )

        return await self._post(
            "/amm/allowances/approve",
            body,
            identity_token,
            with_raw_response,
            AmmAllowanceResponse,
        )

    async def ensure_allowance(
        self,
        params: AmmAllowanceParams,
        identity_token: Optional[str] = None,
        interval: float = _DEFAULT_ALLOWANCE_POLL_INTERVAL,
        max_attempts: int = _DEFAULT_ALLOWANCE_MAX_ATTEMPTS,
    ) -> AmmAllowanceResponse:
        """Check an allowance, approve it at most once when missing, then poll
        :meth:`check_allowance` until confirmation.

        Buy and sell never invoke this workflow automatically. Polls the check
        endpoint (never approve) at a modest interval to respect rate limits.
        """
        if interval <= 0:
            raise ValueError("interval must be a positive number of seconds")
        if not isinstance(max_attempts, int) or max_attempts <= 0:
            raise ValueError("max_attempts must be a positive integer")

        checked = await self.check_allowance(params, identity_token=identity_token)
        if checked.confirmed:
            return checked

        approved = await self.approve_allowance(params, identity_token=identity_token)
        if approved.confirmed:
            return approved

        latest = approved
        for _ in range(max_attempts):
            await asyncio.sleep(interval)
            latest = await self.check_allowance(params, identity_token=identity_token)
            if latest.confirmed:
                return latest

        return latest

    async def buy(
        self,
        params: AmmBuyParams,
        identity_token: Optional[str] = None,
        with_raw_response: bool = False,
    ) -> Union[AmmBuyResponse, HttpRawResponse]:
        """Submit an exact-collateral AMM buy.

        Does not check or submit allowances. Reuse the same ``params`` when
        retrying so the serialized body and idempotency key remain unchanged.
        """
        identity_token = self._prepare_auth("buy_amm_shares", identity_token)
        body = self._build_buy_body(params)

        self._logger.debug(
            "Buying AMM shares",
            {
                "market": body["market"],
                "outcomeIndex": body["outcomeIndex"],
                "onBehalfOf": body.get("onBehalfOf"),
            },
        )

        return await self._post(
            "/amm/buy",
            body,
            identity_token,
            with_raw_response,
            AmmBuyResponse,
        )

    async def sell(
        self,
        params: AmmSellParams,
        identity_token: Optional[str] = None,
        with_raw_response: bool = False,
    ) -> Union[AmmSellResponse, HttpRawResponse]:
        """Submit an exact-collateral-return AMM sell.

        Does not check or submit allowances. Reuse the same ``params`` when
        retrying so the serialized body and idempotency key remain unchanged.
        """
        identity_token = self._prepare_auth("sell_amm_shares", identity_token)
        body = self._build_sell_body(params)

        self._logger.debug(
            "Selling AMM shares",
            {
                "market": body["market"],
                "outcomeIndex": body["outcomeIndex"],
                "onBehalfOf": body.get("onBehalfOf"),
            },
        )

        return await self._post(
            "/amm/sell",
            body,
            identity_token,
            with_raw_response,
            AmmSellResponse,
        )

    # -- transport ---------------------------------------------------------

    async def _post(
        self,
        path: str,
        body: Dict[str, Any],
        identity_token: Optional[str],
        with_raw_response: bool,
        model,
    ) -> Union[Any, HttpRawResponse]:
        if with_raw_response:
            if identity_token:
                return await self._http_client.post_raw_with_identity(
                    path, identity_token, body
                )
            return await self._http_client.post_raw(path, body)

        if identity_token:
            response = await self._http_client.post_with_identity(
                path, identity_token, body
            )
        else:
            response = await self._http_client.post(path, body)
        return model(**response)

    def _prepare_auth(
        self, operation: str, identity_token: Optional[str]
    ) -> Optional[str]:
        if identity_token is not None:
            trimmed = identity_token.strip()
            if not trimmed:
                raise ValueError(f"identity_token is required for {operation}")
            return trimmed

        self._http_client.require_auth(operation)
        if self._http_client.get_hmac_credentials() is None:
            raise ValueError(_AMM_HMAC_ONLY_ERROR)
        return None

    # -- body building / validation ---------------------------------------

    def _build_allowance_body(self, params: AmmAllowanceParams) -> Dict[str, Any]:
        market = self._validate_market(params.market)
        if params.side not in (AMM_SIDE_BUY, AMM_SIDE_SELL):
            raise ValueError("side must be BUY or SELL")
        self._validate_on_behalf_of(params.on_behalf_of)
        return params.model_copy(update={"market": market}).model_dump(
            by_alias=True, exclude_none=True
        )

    def _build_buy_body(self, params: AmmBuyParams) -> Dict[str, Any]:
        market = self._validate_trade_params(
            params.market,
            params.outcome_index,
            params.collateral_amount,
            "collateral_amount",
            params.slippage_bps,
            params.idempotency_key,
            params.on_behalf_of,
        )
        return params.model_copy(update={"market": market}).model_dump(
            by_alias=True, exclude_none=True
        )

    def _build_sell_body(self, params: AmmSellParams) -> Dict[str, Any]:
        market = self._validate_trade_params(
            params.market,
            params.outcome_index,
            params.collateral_return_amount,
            "collateral_return_amount",
            params.slippage_bps,
            params.idempotency_key,
            params.on_behalf_of,
        )
        return params.model_copy(update={"market": market}).model_dump(
            by_alias=True, exclude_none=True
        )

    def _validate_trade_params(
        self,
        market: str,
        outcome_index: int,
        amount: str,
        amount_field: str,
        slippage_bps: Optional[int],
        idempotency_key: str,
        on_behalf_of: Optional[int],
    ) -> str:
        market = self._validate_market(market)
        if outcome_index not in (0, 1):
            raise ValueError("outcome_index must be 0 (YES) or 1 (NO)")
        self._validate_positive_integer(amount, amount_field)
        if slippage_bps is not None:
            if (
                not isinstance(slippage_bps, int)
                or isinstance(slippage_bps, bool)
                or slippage_bps < 0
                or slippage_bps > 1000
            ):
                raise ValueError("slippage_bps must be between 0 and 1000")
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise ValueError("idempotency_key is required")
        if len(idempotency_key) > _AMM_IDEMPOTENCY_KEY_MAX_LENGTH:
            raise ValueError(
                f"idempotency_key must be at most {_AMM_IDEMPOTENCY_KEY_MAX_LENGTH} characters"
            )
        self._validate_on_behalf_of(on_behalf_of)
        return market

    def _validate_market(self, market: str) -> str:
        if not isinstance(market, str):
            raise ValueError("market is required")
        market = market.strip()
        if not market:
            raise ValueError("market is required")
        if len(market) > _AMM_MARKET_MAX_LENGTH:
            raise ValueError(
                f"market must be at most {_AMM_MARKET_MAX_LENGTH} characters"
            )
        return market

    def _validate_positive_integer(self, value: str, field: str) -> None:
        error = (
            f"{field} must be a positive integer string in the collateral token base unit"
        )
        if not isinstance(value, str):
            raise ValueError(error)
        if len(value) > _AMM_AMOUNT_MAX_LENGTH or not _AMM_POSITIVE_INTEGER_RE.fullmatch(
            value
        ):
            raise ValueError(error)
        if int(value) > _AMM_MAX_UINT256:
            raise ValueError(error)

    def _validate_on_behalf_of(self, on_behalf_of: Optional[int]) -> None:
        if on_behalf_of is None:
            return
        if (
            not isinstance(on_behalf_of, int)
            or isinstance(on_behalf_of, bool)
            or on_behalf_of < 1
            or on_behalf_of > _AMM_MAX_ON_BEHALF_OF
        ):
            raise ValueError(
                "on_behalf_of must be a positive 32-bit integer between 1 and 2147483647"
            )
