"""Server-managed wallet request and response types."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RedeemServerWalletInput(BaseModel):
    """POST /portfolio/redeem payload for server-managed wallets."""

    condition_id: str = Field(alias="conditionId")
    on_behalf_of: int = Field(alias="onBehalfOf")

    model_config = ConfigDict(populate_by_name=True)


class WithdrawServerWalletInput(BaseModel):
    """POST /portfolio/withdraw payload for server-managed wallets.

    ``destination`` is optional. When omitted for a child server-wallet
    withdrawal, the API defaults to the authenticated partner smart wallet when
    present, otherwise the authenticated partner account. Explicit destinations
    must be the authenticated partner account, authenticated partner smart
    wallet, or an active withdrawal address allowlisted on the authenticated
    partner profile.
    """

    amount: str
    on_behalf_of: Optional[int] = Field(None, alias="onBehalfOf")
    token: Optional[str] = None
    destination: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class ServerWalletTransactionEnvelope(BaseModel):
    """Common transaction metadata returned by server-wallet operations."""

    hash: str
    user_operation_hash: str = Field(alias="userOperationHash")
    transaction_id: str = Field(alias="transactionId")
    wallet_address: str = Field(alias="walletAddress")

    model_config = ConfigDict(populate_by_name=True)


class RedeemServerWalletResponse(ServerWalletTransactionEnvelope):
    """Response from POST /portfolio/redeem."""

    condition_id: str = Field(alias="conditionId")
    market_id: int = Field(alias="marketId")

    model_config = ConfigDict(populate_by_name=True)


class WithdrawServerWalletResponse(ServerWalletTransactionEnvelope):
    """Response from POST /portfolio/withdraw."""

    token: str
    destination: str
    amount: str

    model_config = ConfigDict(populate_by_name=True)
