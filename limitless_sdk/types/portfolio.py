"""Portfolio-related type definitions."""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict


class Position(BaseModel):
    """User position in a market.

    Attributes:
        market_slug: Market slug identifier
        token_id: Token ID for the position
        balance: Position balance (scaled)
        market_title: Market title
        outcome_title: Outcome title
        price: Current price
        value: Position value in USDC
    """

    market_slug: str = Field(alias="marketSlug")
    token_id: str = Field(alias="tokenId")
    balance: str
    market_title: Optional[str] = Field(None, alias="marketTitle")
    outcome_title: Optional[str] = Field(None, alias="outcomeTitle")
    price: Optional[float] = None
    value: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class HistoryMarketCollateral(BaseModel):
    """Collateral token info inside a history market."""

    symbol: str
    id: str
    decimals: int

    model_config = ConfigDict(populate_by_name=True)


class HistoryMarket(BaseModel):
    """Market snapshot embedded in a history entry."""

    closed: bool = False
    collateral: Optional[HistoryMarketCollateral] = None
    group: Optional[Any] = None
    condition_id: Optional[str] = Field(None, alias="conditionId")
    funding: Optional[str] = None
    id: str = ""
    slug: str = ""
    title: str = ""
    expiration_date: Optional[str] = Field(None, alias="expirationDate")

    model_config = ConfigDict(populate_by_name=True)


class HistoryEntry(BaseModel):
    """User history entry (cursor-based).

    Represents various types of user actions:
    - AMM trades
    - CLOB trades
    - NegRisk trades & conversions

    Attributes:
        block_timestamp: Block timestamp of the transaction
        collateral_amount: Collateral amount involved
        market: Market snapshot for this entry
        outcome_index: Index of the outcome traded
        outcome_token_amount: Single outcome token amount
        outcome_token_amounts: List of outcome token amounts
        outcome_token_price: Price of outcome token (string or number)
        strategy: Trade strategy (e.g. 'Buy', 'Sell')
        transaction_hash: On-chain transaction hash
    """

    block_timestamp: Optional[int] = Field(None, alias="blockTimestamp")
    collateral_amount: Optional[str] = Field(None, alias="collateralAmount")
    market: Optional[HistoryMarket] = None
    outcome_index: Optional[int] = Field(None, alias="outcomeIndex")
    outcome_token_amount: Optional[str] = Field(None, alias="outcomeTokenAmount")
    outcome_token_amounts: Optional[List[str]] = Field(None, alias="outcomeTokenAmounts")
    outcome_token_price: Optional[Any] = Field(None, alias="outcomeTokenPrice")
    strategy: Optional[str] = None
    transaction_hash: Optional[str] = Field(None, alias="transactionHash")

    model_config = ConfigDict(populate_by_name=True)


class HistoryResponse(BaseModel):
    """Cursor-based user history response.

    Attributes:
        data: List of history entries
        next_cursor: Opaque cursor for fetching the next page (None when no more pages)
    """

    data: List[HistoryEntry] = []
    next_cursor: Optional[str] = Field(None, alias="nextCursor")

    model_config = ConfigDict(populate_by_name=True)


class PortfolioResponse(BaseModel):
    """Complete portfolio response.

    Attributes:
        positions: List of user positions
        total_value: Total portfolio value in USDC
    """

    positions: List[Position]
    total_value: Optional[str] = Field(None, alias="totalValue")

    model_config = ConfigDict(populate_by_name=True)
