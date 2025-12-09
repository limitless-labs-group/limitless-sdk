"""Market-related type definitions."""

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class CollateralToken(BaseModel):
    """Collateral token information.

    Attributes:
        address: Token contract address
        decimals: Token decimals
        symbol: Token symbol (e.g., "USDC")
    """

    address: str
    decimals: int
    symbol: str

    model_config = ConfigDict(populate_by_name=True)


class MarketCreator(BaseModel):
    """Market creator information.

    Attributes:
        name: Creator name
        image_uri: Creator image URL (optional)
        link: Creator link URL (optional)
    """

    name: str
    image_uri: Optional[str] = Field(None, alias="imageURI")
    link: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class MarketMetadata(BaseModel):
    """Market metadata.

    Attributes:
        fee: Fee enabled flag
        is_bannered: Banner flag (optional)
        is_poly_arbitrage: Polymarket arbitrage flag (optional)
        should_market_make: Market making flag (optional)
        open_price: Opening price for oracle markets (optional)
    """

    fee: bool
    is_bannered: Optional[bool] = Field(None, alias="isBannered")
    is_poly_arbitrage: Optional[bool] = Field(None, alias="isPolyArbitrage")
    should_market_make: Optional[bool] = Field(None, alias="shouldMarketMake")
    open_price: Optional[str] = Field(None, alias="openPrice")

    model_config = ConfigDict(populate_by_name=True)


class MarketSettings(BaseModel):
    """Market settings for CLOB markets.

    Attributes:
        min_size: Minimum order size
        max_spread: Maximum spread allowed
        daily_reward: Daily reward amount
        rewards_epoch: Rewards epoch duration
        c: Constant parameter
    """

    min_size: str = Field(alias="minSize")
    max_spread: float = Field(alias="maxSpread")
    daily_reward: str = Field(alias="dailyReward")
    rewards_epoch: str = Field(alias="rewardsEpoch")
    c: str

    model_config = ConfigDict(populate_by_name=True)


class TradePrices(BaseModel):
    """Trade prices for different order types.

    Attributes:
        buy: Buy prices (market and limit) for yes/no tokens
        sell: Sell prices (market and limit) for yes/no tokens
    """

    buy: Dict[str, List[float]]
    sell: Dict[str, List[float]]

    model_config = ConfigDict(populate_by_name=True)


class PriceOracleMetadata(BaseModel):
    """Price oracle metadata for oracle-based markets.

    Attributes:
        ticker: Asset ticker symbol
        asset_type: Asset type (e.g., "CRYPTO")
        pyth_address: Pyth Network price feed address
        symbol: Price feed symbol
        name: Asset name
        logo: Logo URL
    """

    ticker: str
    asset_type: str = Field(alias="assetType")
    pyth_address: str = Field(alias="pythAddress")
    symbol: str
    name: str
    logo: str

    model_config = ConfigDict(populate_by_name=True)


class OrderbookEntry(BaseModel):
    """Orderbook entry (bid or ask).
    Matches API response format exactly (1:1 parity).

    Attributes:
        price: Price per share (0-1 range)
        size: Size in shares (scaled by 1e6)
        side: Order side ("BUY" or "SELL")
    """

    price: float
    size: int
    side: str


class OrderBook(BaseModel):
    """Complete orderbook for a market.
    Matches API response format exactly (1:1 parity).

    Attributes:
        bids: List of bid orders (buy orders) sorted by price descending
        asks: List of ask orders (sell orders) sorted by price ascending
        token_id: Token ID for the orderbook (YES token)
        adjusted_midpoint: Adjusted midpoint price between best bid and ask
        max_spread: Maximum allowed spread for the market
        min_size: Minimum order size allowed
        last_trade_price: Last trade price for the market
    """

    bids: List[OrderbookEntry]
    asks: List[OrderbookEntry]
    token_id: str = Field(alias="tokenId")
    adjusted_midpoint: float = Field(alias="adjustedMidpoint")
    max_spread: str = Field(alias="maxSpread")
    min_size: str = Field(alias="minSize")
    last_trade_price: float = Field(alias="lastTradePrice")

    model_config = ConfigDict(populate_by_name=True)


class MarketPrice(BaseModel):
    """Market price information.

    Attributes:
        token_id: Token ID
        price: Current price
        updated_at: Last update timestamp (optional)
    """

    token_id: str = Field(alias="tokenId")
    price: float
    updated_at: Optional[str] = Field(None, alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class MarketOutcome(BaseModel):
    """Market outcome information.

    Attributes:
        id: Outcome ID
        title: Outcome title
        token_id: Token ID for this outcome
        price: Current price (optional)
    """

    id: int
    title: str
    token_id: str = Field(alias="tokenId")
    price: Optional[float] = None

    model_config = ConfigDict(populate_by_name=True)


class MarketTokens(BaseModel):
    """Market token IDs for CLOB markets."""
    yes: str
    no: str

    model_config = ConfigDict(populate_by_name=True)


class Market(BaseModel):
    """Complete market information (1:1 with API response).

    Handles both CLOB single markets and NegRisk group markets.

    Attributes:
        id: Market database ID
        slug: Market slug identifier
        title: Market title
        proxy_title: Market proxy title (optional)
        description: Market description (optional)
        collateral_token: Collateral token information
        expiration_date: Human-readable expiration date
        expiration_timestamp: Expiration timestamp in milliseconds
        expired: Whether market is expired (optional)
        created_at: Creation timestamp
        updated_at: Last update timestamp
        categories: Market categories
        status: Market status
        creator: Creator information
        tags: Market tags
        trade_type: Trade type (clob or amm)
        market_type: Market type (single or group)
        priority_index: Priority index for sorting
        metadata: Market metadata

        # CLOB single market fields
        condition_id: Condition ID (optional, CLOB only)
        neg_risk_request_id: NegRisk request ID (optional, CLOB only)
        tokens: Token IDs for yes/no outcomes (optional, CLOB only)
        prices: Current prices [yes, no] (optional, CLOB only)
        trade_prices: Trade prices for buy/sell market/limit orders (optional, CLOB only)
        is_rewardable: Whether market is rewardable (optional, CLOB only)
        settings: Market settings (optional, CLOB only)
        volume: Trading volume (optional)
        volume_formatted: Formatted trading volume (optional)
        logo: Market logo URL (optional)
        price_oracle_metadata: Price oracle metadata (optional, oracle markets)
        order_in_group: Order within group (optional, group markets)
        winning_outcome_index: Winning outcome index (optional)

        # NegRisk group market fields
        outcome_tokens: Outcome token names (optional, group only)
        og_image_uri: OG image URI (optional, group only)
        neg_risk_market_id: NegRisk market ID (optional, group only)
        markets: Child markets in group (optional, group only)
        daily_reward: Daily reward for group (optional, group only)
    """

    # Common fields (both single and group)
    id: int
    slug: str
    title: str
    proxy_title: Optional[str] = Field(None, alias="proxyTitle")
    description: Optional[str] = None
    collateral_token: CollateralToken = Field(alias="collateralToken")
    expiration_date: str = Field(alias="expirationDate")
    expiration_timestamp: int = Field(alias="expirationTimestamp")
    expired: Optional[bool] = None
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    categories: List[str]
    status: str
    creator: MarketCreator
    tags: List[str]
    trade_type: str = Field(alias="tradeType")
    market_type: str = Field(alias="marketType")
    priority_index: int = Field(alias="priorityIndex")
    metadata: MarketMetadata
    volume: Optional[str] = None
    volume_formatted: Optional[str] = Field(None, alias="volumeFormatted")

    # CLOB single market fields
    condition_id: Optional[str] = Field(None, alias="conditionId")
    neg_risk_request_id: Optional[str] = Field(None, alias="negRiskRequestId")
    tokens: Optional[MarketTokens] = None
    prices: Optional[List[float]] = None
    trade_prices: Optional[TradePrices] = Field(None, alias="tradePrices")
    is_rewardable: Optional[bool] = Field(None, alias="isRewardable")
    settings: Optional[MarketSettings] = None
    logo: Optional[str] = None
    price_oracle_metadata: Optional[PriceOracleMetadata] = Field(None, alias="priceOracleMetadata")
    order_in_group: Optional[int] = Field(None, alias="orderInGroup")
    winning_outcome_index: Optional[int] = Field(None, alias="winningOutcomeIndex")

    # NegRisk group market fields
    outcome_tokens: Optional[List[str]] = Field(None, alias="outcomeTokens")
    og_image_uri: Optional[str] = Field(None, alias="ogImageURI")
    neg_risk_market_id: Optional[str] = Field(None, alias="negRiskMarketId")
    markets: Optional[List["Market"]] = None
    daily_reward: Optional[str] = Field(None, alias="dailyReward")

    # Legacy/deprecated fields (kept for backwards compatibility)
    outcomes: Optional[List[MarketOutcome]] = None
    type: Optional[str] = None
    address: Optional[str] = None
    resolution_date: Optional[str] = Field(None, alias="resolutionDate")

    model_config = ConfigDict(populate_by_name=True)


class MarketsResponse(BaseModel):
    """Markets list response.

    Attributes:
        markets: Array of markets
        total: Total count
        offset: Pagination offset
        limit: Pagination limit
    """

    markets: List[Market]
    total: Optional[int] = None
    offset: Optional[int] = None
    limit: Optional[int] = None


ActiveMarketsSortBy = Literal["lp_rewards", "ending_soon", "newest", "high_value", "liquidity"]


class ActiveMarketsParams(BaseModel):
    """Query parameters for active markets endpoint.

    Attributes:
        limit: Maximum number of markets to return (max 25)
        page: Page number for pagination (starts at 1)
        sort_by: Sort order for markets

    Example:
        >>> params = ActiveMarketsParams(limit=8, page=1, sort_by="lp_rewards")
    """

    limit: Optional[int] = None
    page: Optional[int] = None
    sort_by: Optional[ActiveMarketsSortBy] = Field(None, alias="sortBy")

    model_config = ConfigDict(populate_by_name=True)


class ActiveMarketsResponse(BaseModel):
    """Active markets response from API.

    Attributes:
        data: Array of active markets
        total_markets_count: Total count of active markets
    """

    data: List[Market]
    total_markets_count: int = Field(alias="totalMarketsCount")

    model_config = ConfigDict(populate_by_name=True)
