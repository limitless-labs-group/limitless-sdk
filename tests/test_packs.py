import asyncio
from unittest.mock import AsyncMock, Mock
import pytest
from limitless_sdk.packs import PacksService, pack_min_payout
from limitless_sdk.types.packs import PackBuyParams, PackQuoteParams
from limitless_sdk.api.errors import APIError, ConflictError, RateLimitError
from limitless_sdk import classify_pack_error

PACK = "22222222-2222-4222-8222-222222222222"

def setup():
    http = Mock()
    http.get_hmac_credentials.return_value = {"token_id": "test", "secret": "test"}
    http.get = AsyncMock()
    http.post = AsyncMock()
    service = PacksService(http)
    service._spacing = 0
    return http, service


def params(**changes):
    values = dict(pack_id=PACK, on_behalf_of=123, stake_amount="1000000", min_payout_amount="2000000", deadline="1", idempotency_key="order-1")
    values.update(changes)
    return PackBuyParams(**values)


def position(status="ACTIVE"):
    return dict(id=PACK, status=status, stakeAmount="1000000", collateralDeposited="2000000", multiplierOffered="2.000000", vigPercent="10.00", wallet="0xwallet", createdAt="2026-10-18T00:00:00Z", legs=[])

@pytest.mark.asyncio
async def test_minimal_ineligible_quote():
    http, service = setup()
    http.post.return_value = {"eligible": False, "ineligibleReasons": ["Insufficient depth"]}
    quote = await service.quote(PackQuoteParams(pack_id=PACK, stake_amount="1000000"))
    assert quote.eligible is False
    assert quote.ineligible_reasons == ["Insufficient depth"]
    assert quote.potential_payout is None
    assert quote.legs is None

@pytest.mark.asyncio
async def test_failed_position_recovers_and_exhaustion_preserves_key(monkeypatch):
    monkeypatch.setattr("limitless_sdk.packs.service.asyncio.sleep", AsyncMock())
    http, service = setup()
    http.get.side_effect = [position("FAILED"), position("ACTIVE")]
    assert (await service.wait_for_position(123, PACK, max_attempts=2)).status == "ACTIVE"
    http.get.side_effect = None
    http.get.return_value = position("FAILED")
    with pytest.raises(TimeoutError, match="replay the identical saved buy"):
        await service.wait_for_position(123, PACK, max_attempts=2)
    assert http.get.await_count == 4

@pytest.mark.asyncio
async def test_real_rate_limit_defers_next_call(monkeypatch):
    clock = [100.0]
    waits = []
    async def sleep(delay):
        waits.append(delay)
        clock[0] += delay
    monkeypatch.setattr("limitless_sdk.packs.service.time.monotonic", lambda: clock[0])
    monkeypatch.setattr("limitless_sdk.packs.service.asyncio.sleep", sleep)
    http, service = setup()
    error = RateLimitError(response_data={"retryAfterSeconds": 10})
    http.post.side_effect = [error, {"eligible": False, "ineligibleReasons": ["depth"]}]
    request = PackQuoteParams(pack_id=PACK, stake_amount="1000000")
    with pytest.raises(RateLimitError):
        await service.quote(request)
    assert http.post.await_count == 1
    await service.quote(request)
    assert waits == [0, 10]
    assert http.post.await_count == 2

def test_pack_error_details():
    result = classify_pack_error(ConflictError("approve", response_data={
        "code": "PACK_ALLOWANCE_REQUIRED", "tokenAddress": "0xtoken",
        "spender": "0xvault", "requiredAllowance": "1000000",
    }))
    assert result.kind == "ALLOWANCE_REQUIRED"
    assert (result.token_address, result.spender, result.required_allowance) == ("0xtoken", "0xvault", "1000000")
    result = classify_pack_error(APIError("signature", 400, {
        "code": "BAD_INTENT_SIGNATURE", "submissionState": "NOT_SUBMITTED",
        "parlayId": PACK, "recovery": "Fix cause",
    }))
    assert (result.kind, result.parlay_id, result.recovery) == ("NOT_SUBMITTED", PACK, "Fix cause")
    for status, data, message, kind in [
        (409, {"code": "PRICE_DRIFTED"}, "price", "PRICE_DRIFTED"),
        (401, {}, "Intent expired — please retry", "INTENT_EXPIRED"),
        (401, {}, "Invalid signature", "OTHER"),
        (409, {}, "Another Pack operation is in progress for this wallet; retry the same request", "WALLET_BUSY"),
        (429, {}, "limit", "RATE_LIMITED"),
        (409, {"code": "PACK_TRANSACTION_REVERTED"}, "reverted", "TRANSACTION_REVERTED"),
        (409, {"code": "PACK_SUBMISSION_UNKNOWN", "submissionState": "NOT_SUBMITTED"}, "unknown", "SUBMISSION_UNKNOWN"),
        (500, {"submissionState": "NOT_SUBMITTED"}, "internal", "OTHER"),
        (400, {"submissionState": True}, "malformed", "OTHER"),
    ]:
        assert classify_pack_error(APIError(message, status, data)).kind == kind
    assert classify_pack_error(TimeoutError()).kind == "OTHER"

@pytest.mark.asyncio
async def test_expired_replay_and_wire_headers():
    http, service = setup()
    http.post.return_value = {"status": "RECOVERING", "position": position("PENDING")}
    for _ in range(2):
        assert (await service.buy(params())).status == "RECOVERING"
    assert http.post.await_args_list[0] == http.post.await_args_list[1]
    assert http.post.await_args.args[1]["deadline"] == "1"
    assert http.post.await_args.args[1]["onBehalfOf"] == 123
    http.get.return_value = dict(data=[], total=0, limit=50, offset=0)
    await service.list_positions(123, 100, -1)
    http.get.assert_awaited_once_with("/parlay/partner/positions?limit=50&offset=0", headers={"x-on-behalf-of": "123"})

@pytest.mark.asyncio
async def test_claim_unknown_stops():
    http, service = setup()
    error = ConflictError("find receipt", 409, {"code": "PACK_SUBMISSION_UNKNOWN"}, "/claim", "POST")
    http.post.side_effect = error
    with pytest.raises(ConflictError) as caught:
        await service.claim(123, PACK)
    assert caught.value is error
    assert http.post.await_count == 1

@pytest.mark.asyncio
async def test_minting_terminal_failure_and_cancel():
    http, service = setup()
    http.get.return_value = position("VAULT_REVERTED")
    with pytest.raises(RuntimeError, match="VAULT_REVERTED"):
        await service.wait_for_position(123, PACK)
    service._next = __import__('time').monotonic() + 3600
    task = asyncio.create_task(service.buy(params()))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    http.post.assert_not_awaited()

@pytest.mark.asyncio
async def test_validation_auth_and_precision():
    http, service = setup()
    for amount in ["0", "01", "1e6", "1.5", "9" * 21]:
        with pytest.raises(ValueError):
            await service.buy(params(stake_amount=amount))
    for key in ["", "space key", "é", "x" * 129]:
        with pytest.raises(ValueError):
            await service.buy(params(idempotency_key=key))
    assert pack_min_payout("99999999999999999999", 100) == "98999999999999999999"
    http.get_hmac_credentials.return_value = None
    with pytest.raises(ValueError, match="HMAC"):
        await service.buy(params())
    http.post.assert_not_awaited()
