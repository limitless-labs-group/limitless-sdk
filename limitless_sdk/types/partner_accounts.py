"""Partner-account creation and allowance recovery types."""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CreatePartnerAccountInput(BaseModel):
    """Partner-owned profile creation payload."""

    display_name: Optional[str] = Field(None, alias="displayName")
    create_server_wallet: Optional[bool] = Field(None, alias="createServerWallet")

    model_config = ConfigDict(populate_by_name=True)


class CreatePartnerAccountEOAHeaders(BaseModel):
    """EOA verification headers for partner-account creation."""

    account: str
    signing_message: str = Field(alias="signingMessage")
    signature: str

    model_config = ConfigDict(populate_by_name=True)


class PartnerAccountResponse(BaseModel):
    """Partner-account creation response."""

    profile_id: int = Field(alias="profileId")
    account: str

    model_config = ConfigDict(populate_by_name=True)


class PartnerWithdrawalAddressInput(BaseModel):
    """Request payload for adding a partner withdrawal destination allowlist entry."""

    address: str
    label: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class PartnerWithdrawalAddressResponse(BaseModel):
    """Response returned after adding a partner withdrawal destination allowlist entry."""

    id: str
    profile_id: int = Field(alias="profileId")
    destination_address: str = Field(alias="destinationAddress")
    label: str
    created_at: str = Field(alias="createdAt")
    deleted_at: Optional[str] = Field(None, alias="deletedAt")

    model_config = ConfigDict(populate_by_name=True)


PartnerAccountAllowanceTypeUsdcAllowance = "USDC_ALLOWANCE"
PartnerAccountAllowanceTypeCtfApproval = "CTF_APPROVAL"

PartnerAccountAllowanceRequiredForBuy = "BUY"
PartnerAccountAllowanceRequiredForSell = "SELL"

PartnerAccountAllowanceStatusConfirmed = "confirmed"
PartnerAccountAllowanceStatusMissing = "missing"
PartnerAccountAllowanceStatusSubmitted = "submitted"
PartnerAccountAllowanceStatusFailed = "failed"

PartnerAccountAllowanceErrorPrivySponsorshipUnavailable = (
    "PRIVY_SPONSORSHIP_UNAVAILABLE"
)
PartnerAccountAllowanceErrorPrivySubmissionFailed = "PRIVY_SUBMISSION_FAILED"
PartnerAccountAllowanceErrorRpcReadFailed = "RPC_READ_FAILED"
PartnerAccountAllowanceErrorRequestBudgetExceeded = "REQUEST_BUDGET_EXCEEDED"


class PartnerAccountAllowanceSummary(BaseModel):
    """Aggregate allowance readiness counts."""

    total: int
    confirmed: int
    missing: int
    submitted: int
    failed: int


class PartnerAccountAllowanceTarget(BaseModel):
    """Individual allowance or approval target returned by recovery endpoints."""

    type: str
    token_address: str = Field(alias="tokenAddress")
    spender_or_operator: str = Field(alias="spenderOrOperator")
    label: str
    required_for: str = Field(alias="requiredFor")
    confirmed: bool
    status: str
    transaction_id: Optional[str] = Field(None, alias="transactionId")
    tx_hash: Optional[str] = Field(None, alias="txHash")
    user_operation_hash: Optional[str] = Field(None, alias="userOperationHash")
    retryable: bool
    error_code: Optional[str] = Field(None, alias="errorCode")
    error_message: Optional[str] = Field(None, alias="errorMessage")

    model_config = ConfigDict(populate_by_name=True)


class PartnerAccountAllowanceResponse(BaseModel):
    """Partner server-wallet allowance recovery response."""

    profile_id: int = Field(alias="profileId")
    partner_profile_id: int = Field(alias="partnerProfileId")
    chain_id: int = Field(alias="chainId")
    wallet_address: str = Field(alias="walletAddress")
    ready: bool
    summary: PartnerAccountAllowanceSummary
    targets: List[PartnerAccountAllowanceTarget]

    model_config = ConfigDict(populate_by_name=True)
