"""Partner AMM request and response types.

Wire contract mirrors the Go SDK (``limitless/amm_types.go``) and the shared
AMM contract. Requests serialize with ``model_dump(by_alias=True,
exclude_none=True)`` so optional fields (``slippageBps``, ``onBehalfOf``) are
omitted rather than sent as ``null``.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# Allowance side constants (case-sensitive on the wire).
AMM_SIDE_BUY = "BUY"
AMM_SIDE_SELL = "SELL"

# Allowance status constants (lowercase on the wire).
AMM_ALLOWANCE_STATUS_MISSING = "missing"
AMM_ALLOWANCE_STATUS_SUBMITTED = "submitted"
AMM_ALLOWANCE_STATUS_CONFIRMED = "confirmed"

# Trade submission status (uppercase on the wire).
AMM_TRADE_STATUS_SUBMITTED = "SUBMITTED"

# Binary outcome index constants.
AMM_OUTCOME_YES = 0
AMM_OUTCOME_NO = 1


class AmmAllowanceParams(BaseModel):
    """Selects the wallet, market, and side for an allowance check/approve.

    ``market`` may be a market slug or a checksummed FPMM address. Leave
    ``on_behalf_of`` as ``None`` when the authenticated profile directly owns
    the server wallet.
    """

    market: str
    side: str
    on_behalf_of: Optional[int] = Field(None, alias="onBehalfOf")

    model_config = ConfigDict(populate_by_name=True)


class AmmBuyParams(BaseModel):
    """Exact-collateral AMM buy request.

    ``collateral_amount`` must be a positive integer string in the collateral
    token's base units. ``slippage_bps`` ``None`` uses the API default; ``0``
    explicitly requests zero slippage. ``idempotency_key`` is required and
    retained by the API for 24 hours.
    """

    market: str
    outcome_index: int = Field(alias="outcomeIndex")
    collateral_amount: str = Field(alias="collateralAmount")
    slippage_bps: Optional[int] = Field(None, alias="slippageBps")
    idempotency_key: str = Field(alias="idempotencyKey")
    on_behalf_of: Optional[int] = Field(None, alias="onBehalfOf")

    model_config = ConfigDict(populate_by_name=True)


class AmmSellParams(BaseModel):
    """Exact-collateral-return AMM sell request.

    ``collateral_return_amount`` must be a positive integer string in the
    collateral token's base units. ``slippage_bps`` ``None`` uses the API
    default; ``0`` explicitly requests zero slippage. ``idempotency_key`` is
    required and retained by the API for 24 hours.
    """

    market: str
    outcome_index: int = Field(alias="outcomeIndex")
    collateral_return_amount: str = Field(alias="collateralReturnAmount")
    slippage_bps: Optional[int] = Field(None, alias="slippageBps")
    idempotency_key: str = Field(alias="idempotencyKey")
    on_behalf_of: Optional[int] = Field(None, alias="onBehalfOf")

    model_config = ConfigDict(populate_by_name=True)


class AmmTransactionIdentifiers(BaseModel):
    """Independently optional transaction identifiers.

    Sponsored server-wallet operations often return only a subset (a sponsored
    userop may have no ``txHash``).
    """

    transaction_id: Optional[str] = Field(None, alias="transactionId")
    user_operation_hash: Optional[str] = Field(None, alias="userOperationHash")
    tx_hash: Optional[str] = Field(None, alias="txHash")

    model_config = ConfigDict(populate_by_name=True)


class AmmAllowanceResponse(AmmTransactionIdentifiers):
    """Response from allowance check and approve operations.

    ``current_allowance`` is present for BUY checks and omitted for SELL checks.
    """

    status: str
    confirmed: bool
    market: str
    market_address: str = Field(alias="marketAddress")
    side: str
    wallet_address: str = Field(alias="walletAddress")
    token_address: str = Field(alias="tokenAddress")
    spender_or_operator: str = Field(alias="spenderOrOperator")
    current_allowance: Optional[str] = Field(None, alias="currentAllowance")

    model_config = ConfigDict(populate_by_name=True)


class AmmBuyResponse(AmmTransactionIdentifiers):
    """Response after an AMM buy has been submitted."""

    status: str
    market: str
    outcome_index: int = Field(alias="outcomeIndex")
    collateral_amount: str = Field(alias="collateralAmount")
    expected_shares: str = Field(alias="expectedShares")
    min_shares: str = Field(alias="minShares")

    model_config = ConfigDict(populate_by_name=True)


class AmmSellResponse(AmmTransactionIdentifiers):
    """Response after an AMM sell has been submitted."""

    status: str
    market: str
    outcome_index: int = Field(alias="outcomeIndex")
    collateral_return_amount: str = Field(alias="collateralReturnAmount")
    expected_shares: str = Field(alias="expectedShares")
    max_shares: str = Field(alias="maxShares")

    model_config = ConfigDict(populate_by_name=True)
