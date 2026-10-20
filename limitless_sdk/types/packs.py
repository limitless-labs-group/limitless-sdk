"""Curated Pack wire types. All monetary values are integer micro-USDC strings."""
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class PackModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

class PackLeg(PackModel):
    id: Optional[str] = None
    leg_index: Optional[int] = Field(None, alias="legIndex")
    price_at_creation: Optional[str] = Field(None, alias="priceAtCreation")
    resolution_status: Optional[str] = Field(None, alias="resolutionStatus")
    resolved_at: Optional[str] = Field(None, alias="resolvedAt")
    market_slug: Optional[str] = Field(None, alias="marketSlug")
    market_id: Optional[int] = Field(None, alias="marketId")
    condition_id: Optional[str] = Field(None, alias="conditionId")
    market_type: Optional[str] = Field(None, alias="marketType")
    outcome: str
    price: Optional[float] = None
    book_price: Optional[float] = Field(None, alias="bookPrice")
    live_price: Optional[float] = Field(None, alias="livePrice")

class Pack(PackModel):
    id: str
    name: str
    status: str
    eligible: bool
    parlay_type: str = Field(alias="parlayType")
    legs: List[PackLeg]

class PackQuoteParams(PackModel):
    pack_id: str = Field(alias="packId")
    stake_amount: str = Field(alias="stakeAmount")

class PackQuote(PackModel):
    eligible: bool
    parlay_type: Optional[str] = Field(None, alias="parlayType")
    raw_multiplier: Optional[float] = Field(None, alias="rawMultiplier")
    multiplier: Optional[float] = None
    potential_payout: Optional[str] = Field(None, alias="potentialPayout")
    collateral_required: Optional[str] = Field(None, alias="collateralRequired")
    vig_percent: Optional[float] = Field(None, alias="vigPercent")
    legs: Optional[List[PackLeg]] = None
    ineligible_reasons: Optional[List[str]] = Field(None, alias="ineligibleReasons")

class PackBuyParams(PackQuoteParams):
    """Persist the full body before buying; replay unchanged, even after expiry."""
    on_behalf_of: int = Field(alias="onBehalfOf", strict=True)
    min_payout_amount: str = Field(alias="minPayoutAmount")
    deadline: str
    idempotency_key: str = Field(alias="idempotencyKey")

class PackSource(PackModel):
    id: str
    name: str

class PackPosition(PackModel):
    id: str
    status: str
    stake_amount: str = Field(alias="stakeAmount")
    collateral_deposited: str = Field(alias="collateralDeposited")
    multiplier_offered: str = Field(alias="multiplierOffered")
    vig_percent: str = Field(alias="vigPercent")
    tx_hash: Optional[str] = Field(None, alias="txHash")
    claim_tx_hash: Optional[str] = Field(None, alias="claimTxHash")
    wallet: str
    created_at: str = Field(alias="createdAt")
    legs: List[PackLeg]
    source_pack: Optional[PackSource] = Field(None, alias="sourcePack")
    payout_amount: Optional[str] = Field(None, alias="payoutAmount")

class PackBuyResponse(PackModel):
    status: str
    position: PackPosition

class PackPositions(PackModel):
    data: List[PackPosition]
    total: int
    limit: int
    offset: int

class PackClaimResponse(PackModel):
    parlay_id: str = Field(alias="parlayId")
    status: str
    tx_hash: Optional[str] = Field(None, alias="txHash")
    transaction_id: Optional[str] = Field(None, alias="transactionId")
    user_operation_hash: Optional[str] = Field(None, alias="userOperationHash")
