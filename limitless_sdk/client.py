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
        self.auth_token = None
        self.signing_message = None
    
    async def __aenter__(self):
        """Create session when used as context manager."""
        await self.create_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close session when exiting context manager."""
        await self.close_session()
    
    async def create_session(self):
        """Create an aiohttp session."""
        if self.session is None or self.session.closed:
            headers = {
                "Content-Type": "application/json",
            }
            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=self.timeout
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
        """Login to the API."""
        await self.ensure_session()
        
        # Get signing message if not already obtained
        if not self.signing_message:
            await self.get_signing_message()
        
        # Sign the message
        signature = self.sign_message(self.signing_message)
        
        # Login with the signature
        url = f"{self.base_url}/auth/login"
        payload = {
            "account": self.account.address,
            "signingMessage": self.signing_message,
            "signature": signature,
            "client": "limitless-sdk"
        }
        
        async with self.session.post(url, json=payload) as response:
            if response.status == 201:
                data = await response.json()
                self.auth_token = data.get("token")
                # Add Authorization header to session
                self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
                return True
            else:
                error_text = await response.text()
                if response.status == 429:
                    raise RateLimitError(f"Rate limit exceeded during login: {error_text}", response.status)
                elif response.status == 401:
                    raise AuthenticationError(f"Authentication failed: {error_text}", response.status)
                else:
                    raise LimitlessAPIError(f"Failed to login: {response.status} - {error_text}", response.status)
    
    async def ensure_authenticated(self):
        """Ensure user is authenticated."""
        if not self.auth_token:
            await self.login()
    
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
    async def place_order(self, create_order_dto: CreateOrderDto) -> Dict:
        """Create a new order using the CreateOrderDto.
        
        Args:
            create_order_dto: CreateOrderDto containing order details
            
        Returns:
            Order details
        """
        await self.ensure_authenticated()
        await self.ensure_session()

        url = f"{self.base_url}/orders"
        
        # Convert DTO to dict for API request
        payload = create_order_dto.dict()
        
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
    async def cancel_order(self, cancel_order_dto: CancelOrderDto) -> Dict:
        """Cancel an order using the CancelOrderDto.
        
        Args:
            cancel_order_dto: CancelOrderDto containing order ID
            
        Returns:
            Cancelled order details
        """
        await self.ensure_authenticated()
        await self.ensure_session()
        
        url = f"{self.base_url}/orders/{cancel_order_dto.orderId}"
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
                raise LimitlessAPIError(f"Failed to cancel order: {response.status} - {error_text}", response.status)
    
    @retry_on_rate_limit(max_retries=2, delays=[5, 10])
    async def cancel_order_batch(self, delete_order_batch_dto: DeleteOrderBatchDto) -> Dict:
        """Cancel multiple orders using the DeleteOrderBatchDto.
        
        Args:
            delete_order_batch_dto: DeleteOrderBatchDto containing list of order IDs
            
        Returns:
            List of cancelled order details
        """
        await self.ensure_authenticated()
        await self.ensure_session()
        
        url = f"{self.base_url}/orders/cancel-batch"
        payload = delete_order_batch_dto.dict()
        
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