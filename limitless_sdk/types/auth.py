"""Authentication-related type definitions."""

from typing import Optional, Literal, List, Any
from pydantic import BaseModel, Field, ConfigDict


class UserRank(BaseModel):
    """User rank information.

    Attributes:
        id: Rank ID
        name: Rank name
        fee_rate_bps: Fee rate in basis points
    """

    id: int
    name: str
    fee_rate_bps: int = Field(alias="feeRateBps")

    model_config = ConfigDict(populate_by_name=True)


class ReferralData(BaseModel):
    """Referral data for a user.

    Attributes:
        created_at: Referral creation timestamp
        id: Referral ID
        referred_profile_id: Referred user's profile ID
        pfp_url: Profile picture URL (optional)
        display_name: Display name
    """

    created_at: str = Field(alias="createdAt")
    id: int
    referred_profile_id: int = Field(alias="referredProfileId")
    pfp_url: Optional[str] = Field(None, alias="pfpUrl")
    display_name: str = Field(alias="displayName")

    model_config = ConfigDict(populate_by_name=True)


class LoginOptions(BaseModel):
    """Login configuration options.

    Args:
        client: Authentication client type ('eoa' or 'etherspot')
        smart_wallet: Smart wallet address (required for 'etherspot')

    Example:
        >>> # EOA authentication
        >>> options = LoginOptions(client="eoa")
        >>>
        >>> # Etherspot authentication
        >>> options = LoginOptions(
        ...     client="etherspot",
        ...     smart_wallet="0x..."
        ... )
    """

    client: Literal["eoa", "etherspot"] = "eoa"
    smart_wallet: Optional[str] = Field(None, alias="smartWallet")

    model_config = ConfigDict(populate_by_name=True)


class UserProfile(BaseModel):
    """User profile data from API (1:1 with API response).

    Attributes:
        id: User ID (used as ownerId for orders)
        account: User's Ethereum address
        client: Client type used for authentication
        rank: User rank information containing feeRateBps
        created_at: Account creation timestamp (optional)

        # Profile information
        username: Username (optional)
        display_name: Display name (optional)
        pfp_url: Profile picture URL (optional)
        bio: User bio (optional)
        social_url: Social media URL (optional)
        smart_wallet: Smart wallet address (optional)
        trade_wallet_option: Trade wallet option (optional)
        embedded_account: Embedded account address (optional)

        # Points and gamification
        points: Total points (optional)
        accumulative_points: Accumulative points (optional)
        enrolled_in_points_program: Whether enrolled in points program (optional)
        leaderboard_position: Position on leaderboard (optional)
        is_top100: Whether user is in top 100 (optional)
        is_captain: Whether user is a captain (optional)

        # Referral data
        referral_data: List of referral information (optional)
        referred_users_count: Count of referred users (optional)
    """

    # Core fields
    id: int
    account: str
    client: str
    rank: Optional[UserRank] = None
    created_at: Optional[str] = Field(None, alias="createdAt")

    # Profile information
    username: Optional[str] = None
    display_name: Optional[str] = Field(None, alias="displayName")
    pfp_url: Optional[str] = Field(None, alias="pfpUrl")
    bio: Optional[str] = None
    social_url: Optional[str] = Field(None, alias="socialUrl")
    smart_wallet: Optional[str] = Field(None, alias="smartWallet")
    trade_wallet_option: Optional[str] = Field(None, alias="tradeWalletOption")
    embedded_account: Optional[str] = Field(None, alias="embeddedAccount")

    # Points and gamification
    points: Optional[float] = None
    accumulative_points: Optional[float] = Field(None, alias="accumulativePoints")
    enrolled_in_points_program: Optional[bool] = Field(None, alias="enrolledInPointsProgram")
    leaderboard_position: Optional[int] = Field(None, alias="leaderboardPosition")
    is_top100: Optional[bool] = Field(None, alias="isTop100")
    is_captain: Optional[bool] = Field(None, alias="isCaptain")

    # Referral data
    referral_data: Optional[List[ReferralData]] = Field(None, alias="referralData")
    referred_users_count: Optional[int] = Field(None, alias="referredUsersCount")

    @property
    def fee_rate_bps(self) -> int:
        """Get fee rate from rank, defaulting to 300 if not available."""
        if self.rank and hasattr(self.rank, 'fee_rate_bps'):
            return self.rank.fee_rate_bps
        return 300  # Default 3% fee

    model_config = ConfigDict(populate_by_name=True)


class AuthResult(BaseModel):
    """Authentication result.

    Attributes:
        session_cookie: Session cookie value for authenticated requests
        profile: User profile data
    """

    session_cookie: str
    profile: UserProfile


class UserData(BaseModel):
    """User data for order creation.

    Attributes:
        user_id: User ID (from profile)
        fee_rate_bps: User's fee rate in basis points

    Example:
        >>> from limitless_sdk.types import UserData
        >>> user_data = UserData(user_id=123, fee_rate_bps=300)
    """

    user_id: int
    fee_rate_bps: int
