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


class HistoryEntry(BaseModel):
    """User history entry.

    Represents various types of user actions:
    - AMM trades
    - CLOB trades
    - Token splits/merges
    - NegRisk conversions

    Attributes:
        id: Entry ID
        type: Entry type (trade, split, merge, conversion, etc.)
        created_at: Entry creation timestamp
        market_slug: Associated market slug
        amount: Transaction amount
        details: Additional entry details
    """

    id: str
    type: str
    created_at: str = Field(alias="createdAt")
    market_slug: Optional[str] = Field(None, alias="marketSlug")
    amount: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(populate_by_name=True)


class HistoryResponse(BaseModel):
    """Paginated user history response.

    Attributes:
        data: List of history entries
        total_count: Total number of entries
    """

    data: List[HistoryEntry]
    total_count: int = Field(alias="totalCount")

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
