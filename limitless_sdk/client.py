"""Main client for Limitless Exchange API."""

import asyncio
import logging
import math
import time
from functools import wraps
from typing import Dict, List, Optional, Union, Any

import aiohttp
from eth_account import Account
from eth_account.messages import encode_defunct

from .exceptions import LimitlessAPIError, RateLimitError, AuthenticationError
from .models import (
    CreateOrderDto,
    CancelOrderDto,
    DeleteOrderBatchDto,
    MarketSlugValidator,
)

logger = logging.getLogger(__name__)


def retry_on_rate_limit(max_retries: int = 2, delays: List[int] = None):
    """
    Decorator to retry API calls on rate limiting (429 errors).
    
    Args:
        max_retries: Maximum number of retries (default: 2)
        delays: List of delay times in seconds for each retry (default: [5, 10])
    """
    if delays is None:
        delays = [5, 10]
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            # First attempt
            try:
                return await func(*args, **kwargs)
            except (RateLimitError, aiohttp.ClientResponseError) as e:
                # Check if it's actually a rate limit error
                status_code = getattr(e, 'status_code', getattr(e, 'status', None))
                if status_code != 429:
                    # Not a rate limit error, raise immediately
                    raise e
                last_exception = e
                logger.warning(f"Rate limit hit on {func.__name__} (HTTP {status_code}), starting retry sequence...")
            except (aiohttp.ServerTimeoutError, asyncio.TimeoutError) as e:
                # Don't retry on timeout errors, they're not rate limits
                raise e
            except Exception as e:
                # Check if it's our custom exception pattern with 429 in the message
                if "429" in str(e) and "Too Many Requests" in str(e):
                    last_exception = e
                    logger.warning(f"Rate limit hit on {func.__name__}, starting retry sequence...")
                else:
                    # Not a rate limit error, raise immediately
                    raise e
            
            # Retry attempts
            for attempt in range(max_retries):
                try:
                    delay = delays[attempt] if attempt < len(delays) else delays[-1]
                    logger.info(f"Retrying {func.__name__} after {delay} seconds (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(delay)
                    return await func(*args, **kwargs)
                except (RateLimitError, aiohttp.ClientResponseError) as e:
                    status_code = getattr(e, 'status_code', getattr(e, 'status', None))
                    if status_code != 429:
                        # Not a rate limit error, raise immediately
                        raise e
                    last_exception = e
                    logger.warning(f"Rate limit hit again on {func.__name__}, attempt {attempt + 1}/{max_retries}")
                except (aiohttp.ServerTimeoutError, asyncio.TimeoutError) as e:
                    # Don't retry on timeout errors, they're not rate limits
                    raise e
                except Exception as e:
                    # Check if it's our custom exception pattern with 429 in the message
                    if "429" in str(e) and "Too Many Requests" in str(e):
                        last_exception = e
                        logger.warning(f"Rate limit hit again on {func.__name__}, attempt {attempt + 1}/{max_retries}")
                    else:
                        # Not a rate limit error, raise immediately
                        raise e
            
            # All retries exhausted, raise the last exception
            logger.error(f"All retries exhausted for {func.__name__}, raising last exception")
            raise last_exception
        
        return wrapper
    return decorator


class LimitlessClient:
    """Async client for Limitless Exchange API."""
    
    def __init__(self, private_key: str):
        """Initialize the API client.
        
        Args:
            private_key: Ethereum private key for authentication (required)
        """
        self.base_url = "https://api.limitless.exchange"
        self.private_key = private_key
        self.account = Account.from_key(private_key)
        self.timeout = aiohttp.ClientTimeout(total=30)
        self.session = None
        self.signing_message = None
    
    async def __aenter__(self):
        """Create session when used as context manager."""
        await self.create_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close session when exiting context manager."""
        await self.close_session()
    
    async def create_session(self):
        """Create an aiohttp session with cookie jar."""
        if self.session is None or self.session.closed:
            headers = {
                "Content-Type": "application/json",
            }
            # Create session with cookie jar to automatically handle cookies
            cookie_jar = aiohttp.CookieJar()
            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=self.timeout,
                cookie_jar=cookie_jar
            )
    
    async def close_session(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def ensure_session(self):
        """Ensure session exists."""
        if self.session is None or self.session.closed:
            await self.create_session()
    
    @retry_on_rate_limit(max_retries=2, delays=[5, 10])
    async def get_signing_message(self) -> str:
        """Get a signing message with a randomly generated nonce."""
        await self.ensure_session()
        
        url = f"{self.base_url}/auth/signing-message"
        async with self.session.get(url) as response:
            if response.status == 200:
                # Get the message as plain text, not JSON
                self.signing_message = await response.text()
                return self.signing_message
            elif response.status == 429:
                error_text = await response.text()
                raise RateLimitError(f"Rate limit exceeded: {error_text}", response.status)
            else:
                error_text = await response.text()
                raise LimitlessAPIError(f"Failed to get signing message: {response.status} - {error_text}", response.status)
    
    def sign_message(self, message: str) -> str:
        """Sign a message using the private key."""
        message_hash = encode_defunct(text=message)
        signed_message = self.account.sign_message(message_hash)
        return signed_message.signature.hex()
    
    async def login(self) -> bool:
        """Login to the API using cookie-based authentication."""
        await self.ensure_session()
        
        # Get signing message if not already obtained
        if not self.signing_message:
            await self.get_signing_message()
        
        # Sign the message
        signature = self.sign_message(self.signing_message)
        
        # Login with the signature in headers
        url = f"{self.base_url}/auth/login"
        
        # Payload only contains client type
        payload = {
            "client": "eoa"
        }
        
        # Authentication data goes in headers
        # Hex-encode the signing message to avoid header injection issues with newlines
        hex_signing_message = "0x" + self.signing_message.encode('utf-8').hex()
        
        # Ensure signature has 0x prefix for BytesLike format
        if not signature.startswith("0x"):
            signature = "0x" + signature
        
        headers = {
            "x-account": self.account.address,
            "x-signature": signature,
            "x-signing-message": hex_signing_message
        }
        
        async with self.session.post(url, json=payload, headers=headers) as response:
            response_text = await response.text()
            
            if response.status in [200, 201]:
                # Cookie-based auth: server should set limitless-session cookie
                # aiohttp will automatically store and send it in subsequent requests
                logger.info("Login successful - cookie-based authentication established")
                return True
            elif response.status == 400:
                # Bad request - likely payload structure issue
                logger.error(f"Login failed with bad request: {response_text}")
                logger.info("This might indicate the API expects a different payload structure")
                raise AuthenticationError(f"Authentication payload rejected: {response_text}", response.status)
            elif response.status == 429:
                raise RateLimitError(f"Rate limit exceeded during login: {response_text}", response.status)
            elif response.status == 401:
                raise AuthenticationError(f"Authentication failed: {response_text}", response.status)
            else:
                raise LimitlessAPIError(f"Failed to login: {response.status} - {response_text}", response.status)
    
    async def ensure_authenticated(self):
        """Ensure user is authenticated by checking for limitless-session cookie."""
        # Check if we have the limitless-session cookie
        if self.session and self.session.cookie_jar:
            # Look for limitless-session cookie
            has_session_cookie = False
            for cookie in self.session.cookie_jar:
                if cookie.key == "limitless-session":
                    has_session_cookie = True
                    break
            
            if not has_session_cookie:
                await self.login()
        else:
            await self.login()

    def _generate_salt(self) -> int:
        """Generate a random salt for order."""
        import random
        return random.randint(1, 2**32 - 1)

    def _get_current_timestamp(self) -> int:
        """Get current timestamp."""
        import time
        return int(time.time())

    async def _get_token_id_for_market(self, market_id: str, outcome_index: int = 0) -> str:
        """Get the token ID for a specific market and outcome."""
        # Get market details to find the actual token IDs
        market_details = await self.get_market(market_id)
        tokens = market_details.get('tokens', {})
        
        if outcome_index == 0:  # YES outcome
            token_id = tokens.get('yes')
        else:  # NO outcome  
            token_id = tokens.get('no')
        
        if not token_id:
            raise LimitlessAPIError(f"Could not find token ID for market {market_id} outcome {outcome_index}", 400)
        
        logger.info(f"Found token ID for outcome {outcome_index}: {token_id}")
        return token_id

    async def _calculate_amounts(self, price: float, amount: float, side: int) -> tuple[str, str]:
        """Calculate maker and taker amounts based on price and amount."""
        # USDC has 6 decimals, so scale amounts appropriately
        usdc_decimals = 6
        
        if side == 0:  # BUY
            # When buying, we provide USDC (maker amount) to get shares (taker amount)
            # Based on UI payload: maker=USDC paid, taker=shares received
            usdc_amount = amount * (10 ** usdc_decimals)  # USDC we're paying
            shares_amount = (amount / price) * (10 ** usdc_decimals)  # Shares we're getting
            maker_amount = str(int(usdc_amount))  # USDC paid
            taker_amount = str(int(shares_amount))  # Shares received
        else:  # SELL
            # When selling, we provide shares (maker amount) to get USDC (taker amount)
            shares_amount = (amount / price) * (10 ** usdc_decimals)  # Shares we're selling
            usdc_amount = amount * (10 ** usdc_decimals)  # USDC we're getting
            maker_amount = str(int(shares_amount))  # Shares sold
            taker_amount = str(int(usdc_amount))  # USDC received
        
        logger.info(f"Calculated amounts - Maker: {maker_amount}, Taker: {taker_amount}")
        return maker_amount, taker_amount

    @retry_on_rate_limit(max_retries=2, delays=[5, 10])
    async def get_user_profile(self, account_address: str = None) -> Dict:
        """Get user profile by account address.
        
        Args:
            account_address: Account address (defaults to current user's address)
            
        Returns:
            User profile data including id (which is used as ownerId)
        """
        await self.ensure_session()
        
        # Use current user's address if not specified
        if account_address is None:
            account_address = self.account.address
        
        url = f"{self.base_url}/profiles/{account_address}"
        async with self.session.get(url) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 429:
                error_text = await response.text()
                raise RateLimitError(f"Rate limit exceeded: {error_text}", response.status)
            elif response.status == 404:
                error_text = await response.text()
                raise LimitlessAPIError(f"User profile not found: {error_text}", response.status)
            else:
                error_text = await response.text()
                raise LimitlessAPIError(f"Failed to get user profile: {response.status} - {error_text}", response.status)

    def _sign_order(self, order: "Order", is_negrisk: bool = False) -> str:
        """Sign an order using EIP-712 with the correct Limitless Exchange parameters."""
        from eth_account.messages import encode_typed_data
        
        # Protocol constants
        _PROTOCOL_NAME = "Limitless CTF Exchange"
        _PROTOCOL_VERSION = "1"
        
        # Network configurations
        NETWORK_CONFIG = {
            "testnet": {
                "chain_id": 84532,  # Base Sepolia
                "contract_addr": "0xf636e12bb161895453a0c4e312c47319a295913b",
                "negrisk_addr": "0x9d3891970f5E23E911882be926c632a77AA2f7d0"  # Same for testnet
            },
            "mainnet": {
                "chain_id": 8453,   # Base Mainnet  
                "contract_addr": "0xa4409D988CA2218d956BeEFD3874100F444f0DC3",
                "negrisk_addr": "0x5a38afc17F7E97ad8d6C547ddb837E40B4aEDfC6"  # NegRisk contract
            }
        }
        
        # Use mainnet by default (can be made configurable later)
        network = "mainnet"
        config = NETWORK_CONFIG[network]
        chain_id = config["chain_id"]
        
        # Use the correct contract address based on market type
        if is_negrisk:
            contract_addr = config["negrisk_addr"]
            logger.info(f"🔍 Using NegRisk contract for group market: {contract_addr}")
        else:
            contract_addr = config["contract_addr"]
            logger.info(f"🔍 Using regular contract for single market: {contract_addr}")
        
        # Define domain data for EIP-712 signing
        domain_data = {
            "name": _PROTOCOL_NAME,
            "version": _PROTOCOL_VERSION,
            "chainId": chain_id,
            "verifyingContract": contract_addr
        }
        
        # Define message types
        message_types = {
            "Order": [
                {"name": "salt", "type": "uint256"},
                {"name": "maker", "type": "address"},
                {"name": "signer", "type": "address"},
                {"name": "taker", "type": "address"},
                {"name": "tokenId", "type": "uint256"},
                {"name": "makerAmount", "type": "uint256"},
                {"name": "takerAmount", "type": "uint256"},
                {"name": "expiration", "type": "uint256"},
                {"name": "nonce", "type": "uint256"},
                {"name": "feeRateBps", "type": "uint256"},
                {"name": "side", "type": "uint8"},
                {"name": "signatureType", "type": "uint8"}
            ]
        }
        
        # Define message data
        message_data = {
            "salt": order.salt,
            "maker": order.maker,
            "signer": order.signer,
            "taker": order.taker or "0x0000000000000000000000000000000000000000",
            "tokenId": int(order.tokenId),
            "makerAmount": order.makerAmount,
            "takerAmount": order.takerAmount,
            "expiration": int(order.expiration) if order.expiration else 0,
            "nonce": order.nonce or 0,
            "feeRateBps": order.feeRateBps,
            "side": order.side,
            "signatureType": order.signatureType
        }
        
        # Sign using eth_account's implementation of EIP-712
        encoded_message = encode_typed_data(domain_data, message_types, message_data)
        signed_message = self.account.sign_message(encoded_message)
        
        # Extract signature with 0x prefix
        signature = signed_message.signature.hex()
        if not signature.startswith('0x'):
            signature = '0x' + signature
            
        logger.info(f"✅ EIP-712 signature generated using {network} network (chain {chain_id})")
        return signature

    async def create_order(
        self,
        market_id: str,
        market_slug: str,
        outcome_index: int,
        side: int,  # 0 for BUY, 1 for SELL
        amount: float,  # Amount in USDC
        price: float,  # Price between 0 and 1
        order_type: str = "GTC"
    ) -> "CreateOrderDto":
        """Create a properly constructed CreateOrderDto."""
        from .models import Order, CreateOrderDto, SignatureType
        
        # Get user profile to obtain ownerId
        user_profile = await self.get_user_profile()
        owner_id = user_profile.get('id')
        
        if not owner_id:
            raise LimitlessAPIError("Could not get user ID from profile", 400)
        
        logger.info(f"Using ownerId: {owner_id} from user profile")
        
        # Generate order parameters
        salt = self._generate_salt()
        current_time = self._get_current_timestamp()
        expiration = "0"  # Use "0" for no expiration like the UI
        nonce = 0
        
        # Get the real token ID from market data
        token_id = await self._get_token_id_for_market(market_slug, outcome_index)
        
        # Check if this is a group/negrisk market
        market_details = await self.get_market(market_slug)
        is_negrisk = (
            market_details.get('marketType') == 'group' or
            market_details.get('negRiskRequestId') is not None or
            'negRisk' in str(market_details.get('negRiskMarketId', ''))
        )
        
        if is_negrisk:
            logger.info("🔍 Detected group/negrisk market - will use NegRisk contract for signing")
        else:
            logger.info("🔍 Detected regular market - will use standard contract for signing")
        
        # Calculate amounts as integers (scaled by 6 decimals for USDC)
        maker_amount, taker_amount = await self._calculate_amounts(price, amount, side)
        
        # Create the order object without signature first
        order = Order(
            salt=salt,
            maker=self.account.address,
            signer=self.account.address,
            tokenId=token_id,  # Use the real token ID
            makerAmount=int(maker_amount),
            takerAmount=int(taker_amount),
            feeRateBps=300,  # 3% fee
            side=side,
            signature="0x",  # Will be filled after signing
            signatureType=0,  # EOA
            taker="0x0000000000000000000000000000000000000000",
            expiration=expiration,
            nonce=nonce,
            price=price
        )
        
        # Generate the proper signature
        logger.info("🔐 Generating EIP-712 order signature...")
        signature = self._sign_order(order, is_negrisk=is_negrisk)
        
        # Update the order with the real signature
        order.signature = signature
        
        logger.info(f"✅ Order signature generated: {signature[:20]}...")
        
        # Create the DTO
        create_order_dto = CreateOrderDto(
            order=order,
            ownerId=owner_id,
            orderType=order_type,
            marketSlug=market_slug
        )
        
        return create_order_dto
    
    async def get_all_active_markets(self) -> List[Dict]:
        """Get all active markets."""
        await self.ensure_session()
        
        data = await self.get_active_markets(page=1, limit=10)
        rest_pages = math.ceil(data['totalMarketsCount'] / 10) - 1
        all_markets_data = data['data']

        for page in range(2, rest_pages + 2):
            data = await self.get_active_markets(page=page, limit=10)
            all_markets_data.extend(data['data'])

        return all_markets_data

    @retry_on_rate_limit(max_retries=2, delays=[5, 10])
    async def get_active_markets(self, page: int = 1, limit: int = 10) -> Dict:
        """Get active markets with pagination.
        
        Args:
            page: Page number for pagination (default: 1)
            limit: Number of items per page (default: 10)
        """
        await self.ensure_session()
        
        url = f"{self.base_url}/markets/active?page={page}&limit={limit}"
        async with self.session.get(url) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 429:
                error_text = await response.text()
                raise RateLimitError(f"Rate limit exceeded: {error_text}", response.status)
            else:
                error_text = await response.text()
                raise LimitlessAPIError(f"Failed to get markets: {response.status} - {error_text}", response.status)

    @retry_on_rate_limit(max_retries=2, delays=[5, 10])
    async def get_markets(self) -> List[Dict]:
        """Get all markets."""
        await self.ensure_session()
        
        url = f"{self.base_url}/markets"
        async with self.session.get(url) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 429:
                error_text = await response.text()
                raise RateLimitError(f"Rate limit exceeded: {error_text}", response.status)
            else:
                error_text = await response.text()
                raise LimitlessAPIError(f"Failed to get markets: {response.status} - {error_text}", response.status)
    
    @retry_on_rate_limit(max_retries=2, delays=[5, 10])
    async def get_market(self, slug_or_address: str) -> Dict:
        """Get a specific market by slug or address."""
        await self.ensure_session()
        
        url = f"{self.base_url}/markets/{slug_or_address}"
        async with self.session.get(url) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 429:
                error_text = await response.text()
                raise RateLimitError(f"Rate limit exceeded: {error_text}", response.status)
            else:
                error_text = await response.text()
                raise LimitlessAPIError(f"Failed to get market: {response.status} - {error_text}", response.status)
    
    @retry_on_rate_limit(max_retries=2, delays=[5, 10])
    async def get_historical_prices(self, slug_or_address: str, interval: str = "all") -> tuple[Dict, str]:
        """Get the historical probability of a specific market by slug or address."""
        await self.ensure_session()

        url = f"{self.base_url}/markets/{slug_or_address}/historical-price?interval={interval}"
        
        async with self.session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                
                # Extract the prices array from the response
                prices = data.get("prices", [])
                
                # Handle insufficient data case
                if not prices or len(prices) < 2:
                    return data, "unknown"
                
                # Calculate time difference between first two data points
                timestamps = [int(item["timestamp"]) for item in prices[:2]]
                time_diff = abs(timestamps[1] - timestamps[0]) / 1000  # Convert to seconds
                
                # Map time differences to intervals
                if time_diff <= 60:  # 1 minute
                    data_actual_interval = "1m"
                elif time_diff <= 300:  # 5 minutes
                    data_actual_interval = "5m"
                elif time_diff <= 900:  # 15 minutes
                    data_actual_interval = "15m"
                elif time_diff <= 1800:  # 30 minutes
                    data_actual_interval = "30m"
                elif time_diff <= 43200:  # 12 hours
                    data_actual_interval = "12h"
                else:
                    data_actual_interval = "unknown"
                
                return data, data_actual_interval
            elif response.status == 429:
                error_text = await response.text()
                raise RateLimitError(f"Rate limit exceeded: {error_text}", response.status)
            else:
                error_text = await response.text()
                raise LimitlessAPIError(f"Failed to get historical prices for market: {response.status} - {error_text}", response.status)
    
    @retry_on_rate_limit(max_retries=2, delays=[5, 10])
    async def get_orderbook(self, slug: str) -> Dict:
        """Get the orderbook for a market."""
        await self.ensure_session()
        
        url = f"{self.base_url}/markets/{slug}/orderbook"
        async with self.session.get(url) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 429:
                error_text = await response.text()
                raise RateLimitError(f"Rate limit exceeded: {error_text}", response.status)
            elif response.status == 500:
                error_text = await response.text()
                # Server-side error - log but don't crash the whole operation
                logger.warning(f"Orderbook temporarily unavailable for {slug}: {error_text}")
                raise LimitlessAPIError(f"Orderbook server error for {slug}: {error_text}", response.status)
            else:
                error_text = await response.text()
                raise LimitlessAPIError(f"Failed to get orderbook: {response.status} - {error_text}", response.status)
    
    @retry_on_rate_limit(max_retries=2, delays=[5, 10])
    async def get_user_orders(self, slug: str) -> List[Dict]:
        """Get user's orders for a specific market."""
        await self.ensure_authenticated()
        await self.ensure_session()
        
        url = f"{self.base_url}/markets/{slug}/user-orders"
        async with self.session.get(url) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 429:
                error_text = await response.text()
                raise RateLimitError(f"Rate limit exceeded: {error_text}", response.status)
            elif response.status == 401:
                raise AuthenticationError(f"Unauthorized: {await response.text()}", response.status)
            else:
                error_text = await response.text()
                raise LimitlessAPIError(f"Failed to get user orders: {response.status} - {error_text}", response.status)
    
    @retry_on_rate_limit(max_retries=2, delays=[5, 10])
    async def get_positions(self) -> List[Dict]:
        """Get all positions for the authenticated user."""
        await self.ensure_authenticated()
        await self.ensure_session()
        
        url = f"{self.base_url}/portfolio/positions"
        async with self.session.get(url) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 429:
                error_text = await response.text()
                raise RateLimitError(f"Rate limit exceeded: {error_text}", response.status)
            elif response.status == 401:
                raise AuthenticationError(f"Unauthorized: {await response.text()}", response.status)
            else:
                error_text = await response.text()
                raise LimitlessAPIError(f"Failed to get positions: {response.status} - {error_text}", response.status)
    
    @retry_on_rate_limit(max_retries=2, delays=[5, 10])
    async def get_user_history(self, page: int, limit: int) -> Dict[str, Union[List[Dict], int]]:
        """Get paginated history of user actions.
        
        Includes AMM, CLOB trades, splits/merges, NegRisk conversions.
        
        Args:
            page: Page number (required)
            limit: Number of items per page (required)
            
        Returns:
            Dictionary containing:
                - data: List of history entries
                - totalCount: Total count of entries
        """
        await self.ensure_authenticated()
        await self.ensure_session()
        
        url = f"{self.base_url}/portfolio/history"
        params = {
            "page": page,
            "limit": limit
        }
        
        async with self.session.get(url, params=params) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 400:
                error_text = await response.text()
                raise LimitlessAPIError(f"Invalid pagination parameters: {error_text}", response.status)
            elif response.status == 401:
                raise AuthenticationError(f"Unauthorized: {await response.text()}", response.status)
            elif response.status == 429:
                error_text = await response.text()
                raise RateLimitError(f"Rate limit exceeded: {error_text}", response.status)
            else:
                error_text = await response.text()
                raise LimitlessAPIError(f"Failed to get user history: {response.status} - {error_text}", response.status)
    
    @retry_on_rate_limit(max_retries=2, delays=[5, 10])
    async def place_order(self, create_order_dto: "CreateOrderDto") -> Dict:
        """Create a new order using the CreateOrderDto.
        
        Args:
            create_order_dto: CreateOrderDto containing order details
            
        Returns:
            Order details
        """
        await self.ensure_authenticated()
        await self.ensure_session()

        url = f"{self.base_url}/orders"
        
        # Convert dataclass to dict for API request
        from dataclasses import asdict
        payload = asdict(create_order_dto)
        
        async with self.session.post(url, json=payload) as response:
            if response.status == 201:
                return await response.json()
            elif response.status == 401:
                raise AuthenticationError(f"Unauthorized: {await response.text()}", response.status)
            elif response.status == 429:
                error_text = await response.text()
                raise RateLimitError(f"Rate limit exceeded: {error_text}", response.status)
            else:
                error_text = await response.text()
                raise LimitlessAPIError(f"Failed to create order: {response.status} - {error_text}", response.status)
    
    @retry_on_rate_limit(max_retries=2, delays=[5, 10])
    async def cancel_order(self, cancel_order_dto: "CancelOrderDto") -> Dict:
        """Cancel an order using the CancelOrderDto.
        
        Args:
            cancel_order_dto: CancelOrderDto containing order ID
            
        Returns:
            Cancelled order details
        """
        await self.ensure_authenticated()
        await self.ensure_session()
        
        url = f"{self.base_url}/orders/{cancel_order_dto.order_id}"
        
        # For DELETE requests, we need to avoid sending Content-Type header
        # Create a new request without the default session headers
        async with aiohttp.ClientSession(
            timeout=self.timeout,
            cookie_jar=self.session.cookie_jar  # Keep the cookies for auth
        ) as delete_session:
            async with delete_session.delete(url) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    raise AuthenticationError(f"Unauthorized: {await response.text()}", response.status)
                elif response.status == 429:
                    error_text = await response.text()
                    raise RateLimitError(f"Rate limit exceeded: {error_text}", response.status)
                else:
                    error_text = await response.text()
                    raise LimitlessAPIError(f"Failed to cancel order: {response.status} - {error_text}", response.status)
    
    @retry_on_rate_limit(max_retries=2, delays=[5, 10])
    async def cancel_order_batch(self, delete_order_batch_dto: "DeleteOrderBatchDto") -> Dict:
        """Cancel multiple orders using the DeleteOrderBatchDto.
        
        Args:
            delete_order_batch_dto: DeleteOrderBatchDto containing list of order IDs
            
        Returns:
            List of cancelled order details
        """
        await self.ensure_authenticated()
        await self.ensure_session()
        
        url = f"{self.base_url}/orders/cancel-batch"
        
        # Convert dataclass to dict for API request
        from dataclasses import asdict
        payload = asdict(delete_order_batch_dto)
        
        # This is a POST request so we can use the normal session with JSON headers
        async with self.session.post(url, json=payload) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 401:
                raise AuthenticationError(f"Unauthorized: {await response.text()}", response.status)
            elif response.status == 429:
                error_text = await response.text()
                raise RateLimitError(f"Rate limit exceeded: {error_text}", response.status)
            else:
                error_text = await response.text()
                raise LimitlessAPIError(f"Failed to cancel orders batch: {response.status} - {error_text}", response.status)
    
    @retry_on_rate_limit(max_retries=2, delays=[5, 10])
    async def cancel_all_orders(self, market_slug_validator: MarketSlugValidator) -> Dict:
        """Cancel all orders for a specific market using MarketSlugValidator.
        
        Args:
            market_slug_validator: MarketSlugValidator containing market slug
            
        Returns:
            List of cancelled order details
        """
        await self.ensure_authenticated()
        await self.ensure_session()
        
        url = f"{self.base_url}/orders/all/{market_slug_validator.slug}"
        async with self.session.delete(url) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 401:
                raise AuthenticationError(f"Unauthorized: {await response.text()}", response.status)
            elif response.status == 429:
                error_text = await response.text()
                raise RateLimitError(f"Rate limit exceeded: {error_text}", response.status)
            else:
                error_text = await response.text()
                raise LimitlessAPIError(f"Failed to cancel all orders: {response.status} - {error_text}", response.status) 