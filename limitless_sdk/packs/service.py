"""Partner curated Packs: one-shot writes and bounded convergence helpers."""
import asyncio
import math
import re
import time
from typing import List
from urllib.parse import quote
from ..api.http_client import HttpClient
from ..api.errors import RateLimitError
from ..types.packs import (
    Pack, PackQuoteParams, PackQuote, PackBuyParams, PackBuyResponse,
    PackPosition, PackPositions, PackClaimResponse,
)


def _amount(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", value):
        raise ValueError("Pack amounts and deadlines must be positive integer strings of at most 20 digits")


def _id(value: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", value):
        raise ValueError("Pack/position ID must be a UUID")
    return value


def _profile(value: int) -> None:
    if type(value) is not int or not 1 <= value <= 2147483647:
        raise ValueError("on_behalf_of must be a positive 32-bit integer")


def pack_min_payout(payout: str, slippage_bps: int) -> str:
    """Floor slippage-adjusted payout without floating point arithmetic."""
    _amount(payout)
    if type(slippage_bps) is not int or not 0 <= slippage_bps < 10000:
        raise ValueError("slippage_bps must be between 0 and 9999")
    result = int(payout) * (10000 - slippage_bps) // 10000
    if result == 0:
        raise ValueError("minimum payout rounds to zero")
    return str(result)


class PacksService:
    """Reuse one instance per partner/event loop. Calls are serialized and paced
    below 10 per 10 seconds. No write retries or automatic idempotency keys.
    Persist PackBuyParams in application storage before buy().
    """
    def __init__(self, http_client: HttpClient):
        self._http = http_client
        self._lock = None  # Created on first use inside the owning event loop.
        self._next = 0.0
        self._spacing = 1.1

    async def _call(self, method, path, body=None, on_behalf_of=None):
        if path.startswith("/parlay/partner/") and not self._http.get_hmac_credentials():
            raise ValueError("partner Packs require HMAC credentials with trading and delegated_signing scopes")
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            await asyncio.sleep(max(0, self._next - time.monotonic()))
            self._next = time.monotonic() + self._spacing
            headers = {"x-on-behalf-of": str(on_behalf_of)} if on_behalf_of is not None else None
            try:
                if method == "GET":
                    return await self._http.get(path, headers=headers)
                return await self._http.post(path, body)
            except Exception as error:
                if isinstance(error, RateLimitError) or getattr(error, "status_code", None) == 429:
                    self._next = time.monotonic() + 10
                raise

    async def list(self) -> List[Pack]:
        return [Pack.model_validate(x) for x in await self._call("GET", "/parlay/packs")]

    async def search(self, query: str) -> List[Pack]:
        return [Pack.model_validate(x) for x in await self._call("GET", "/parlay/packs/search?query=" + quote(query, safe=""))]

    async def get(self, pack_id: str) -> Pack:
        return Pack.model_validate(await self._call("GET", "/parlay/packs/" + _id(pack_id)))

    async def quote(self, params: PackQuoteParams) -> PackQuote:
        _id(params.pack_id)
        _amount(params.stake_amount)
        return PackQuote.model_validate(await self._call("POST", "/parlay/partner/quote", params.model_dump(by_alias=True)))

    async def buy(self, params: PackBuyParams) -> PackBuyResponse:
        _profile(params.on_behalf_of)
        _id(params.pack_id)
        for value in (params.stake_amount, params.min_payout_amount, params.deadline):
            _amount(value)
        if not re.fullmatch(r"[\x21-\x7e]{1,128}", params.idempotency_key):
            raise ValueError("idempotency_key must contain 1 to 128 printable ASCII characters without spaces")
        if len(params.deadline) > 12:
            raise ValueError("deadline must contain at most 12 digits")
        # Snapshot before queueing. Do not reject an expired replay.
        body = params.model_dump(by_alias=True)
        return PackBuyResponse.model_validate(await self._call("POST", "/parlay/partner/buy", body))

    async def list_positions(self, on_behalf_of: int, limit: int = 20, offset: int = 0) -> PackPositions:
        _profile(on_behalf_of)
        if type(limit) is not int or type(offset) is not int:
            raise ValueError("limit and offset must be integers")
        path = f"/parlay/partner/positions?limit={max(1, min(50, limit))}&offset={max(0, min(5000, offset))}"
        return PackPositions.model_validate(await self._call("GET", path, on_behalf_of=on_behalf_of))

    async def get_position(self, on_behalf_of: int, position_id: str) -> PackPosition:
        _profile(on_behalf_of)
        return PackPosition.model_validate(await self._call("GET", "/parlay/partner/positions/" + _id(position_id), on_behalf_of=on_behalf_of))

    async def wait_for_position(self, on_behalf_of: int, position_id: str, *, max_attempts: int = 60, interval: float = 5) -> PackPosition:
        """Wait for minting, not market settlement. Cancellation propagates."""
        async def step():
            result = await self.get_position(on_behalf_of, position_id)
            if result.status in ("ACTIVE", "WON", "LOST"):
                return result
            if result.status not in ("PENDING", "FAILED"):
                raise RuntimeError(f"Pack position {position_id} is {result.status}")
        return await self._poll(step, max_attempts, interval, "Pack mint polling exhausted; replay the identical saved buy to distinguish NOT_SUBMITTED from recovery; do not rotate its key")

    async def claim_once(self, on_behalf_of: int, position_id: str) -> PackClaimResponse:
        _profile(on_behalf_of)
        return PackClaimResponse.model_validate(await self._call("POST", "/parlay/partner/positions/" + _id(position_id) + "/claim", {"onBehalfOf": on_behalf_of}))

    async def claim(self, on_behalf_of: int, position_id: str, *, max_attempts: int = 60, interval: float = 5) -> PackClaimResponse:
        """Stop on all errors, including PACK_SUBMISSION_UNKNOWN; use confirm_claim with a mined receipt."""
        async def step():
            result = await self.claim_once(on_behalf_of, position_id)
            if result.status == "CLAIMED":
                return result
            if result.status not in ("APPROVAL_PENDING", "CLAIM_PENDING"):
                raise RuntimeError(f"unknown Pack claim status {result.status}")
        return await self._poll(step, max_attempts, interval)

    async def confirm_claim(self, on_behalf_of: int, position_id: str, tx_hash: str) -> PackClaimResponse:
        _profile(on_behalf_of)
        if not re.fullmatch(r"0x[0-9a-fA-F]{64}", tx_hash):
            raise ValueError("tx_hash must be a mined transaction hash")
        return PackClaimResponse.model_validate(await self._call("POST", "/parlay/partner/positions/" + _id(position_id) + "/claim/confirm", {"onBehalfOf": on_behalf_of, "txHash": tx_hash}))

    async def _poll(self, step, max_attempts, interval, exhausted="Pack polling exhausted; resume with the same position/request"):
        if type(max_attempts) is not int or max_attempts < 1 or not math.isfinite(interval) or interval < 1:
            raise ValueError("polling requires positive max_attempts and interval >= 1 second")
        for attempt in range(max_attempts):
            result = await step()
            if result is not None:
                return result
            if attempt + 1 < max_attempts:
                await asyncio.sleep(interval)
        raise TimeoutError(exhausted)
