# Limitless Exchange Python SDK

A minimalistic, async Python SDK for interacting with the Limitless Exchange API.

## Features

- 🔐 **Ethereum wallet authentication** - EIP-712 message signing with EOA support
- 📈 **Market data access** - Markets, orderbooks, and historical data
- 📋 **Order management** - GTC and FOK orders with automatic signing
- 💼 **Portfolio tracking** - Positions and trading history
- 🔄 **Automatic retries** - Configurable retry logic with session re-authentication
- 🌐 **WebSocket support** - Real-time orderbook updates
- 🛡️ **Custom headers** - Global and per-request header configuration
- ⚡ **Async/await support** - Modern async Python with aiohttp
- 🚀 **Venue caching** - Automatic contract address caching for optimized order creation

## Installation

```bash
pip install limitless-sdk
```

## Quick Start

```python
import asyncio
import os
from eth_account import Account
from limitless_sdk.api import HttpClient
from limitless_sdk.auth import MessageSigner, Authenticator
from limitless_sdk.markets import MarketFetcher
from limitless_sdk.portfolio import PortfolioFetcher
from limitless_sdk.types import LoginOptions

async def main():
    # Setup
    account = Account.from_key(os.getenv("PRIVATE_KEY"))
    http_client = HttpClient(base_url="https://api.limitless.exchange")

    try:
        # Authenticate
        signer = MessageSigner(account)
        authenticator = Authenticator(http_client, signer)
        result = await authenticator.authenticate(LoginOptions(client="eoa"))

        print(f"Authenticated: {result.profile.account}")

        # Get markets
        market_fetcher = MarketFetcher(http_client)
        markets = await market_fetcher.get_markets()
        print(f"Found {markets['totalCount']} markets")

        # Fetch specific market (caches venue data for orders)
        market = await market_fetcher.get_market("bitcoin-2024")
        print(f"Market: {market.title}")

        # Get positions
        portfolio_fetcher = PortfolioFetcher(http_client)
        positions = await portfolio_fetcher.get_positions()
        print(f"CLOB positions: {len(positions['clob'])}")

    finally:
        await http_client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## Authentication

The SDK uses EIP-712 message signing for authentication with EOA (Externally Owned Account) wallets.

### Basic Authentication

```python
from eth_account import Account
from limitless_sdk.api import HttpClient
from limitless_sdk.auth import MessageSigner, Authenticator
from limitless_sdk.types import LoginOptions

# Create account from private key
account = Account.from_key("0x...")

# Initialize HTTP client
http_client = HttpClient(base_url="https://api.limitless.exchange")

# Authenticate
signer = MessageSigner(account)
authenticator = Authenticator(http_client, signer)
result = await authenticator.authenticate(LoginOptions(client="eoa"))

# Access session
print(f"User ID: {result.profile.id}")
print(f"Session: {result.session_cookie[:32]}...")
```

### Custom HTTP Headers

You can configure custom headers globally (applied to ALL requests) or per-request:

```python
# Global headers (rate limiting bypass, custom auth, etc.)
http_client = HttpClient(
    base_url="https://api.limitless.exchange",
    additional_headers={
        "X-Rate-Limit-Bypass": "your-secret-token",
        "X-API-Version": "v1"
    }
)

# Per-request headers (request ID, tracing, etc.)
response = await http_client.get("/endpoint", headers={"X-Request-ID": "123"})
```

### Auto-Retry on Session Expiration

The `AuthenticatedClient` wrapper automatically re-authenticates when sessions expire:

```python
from limitless_sdk.auth import AuthenticatedClient

auth_client = AuthenticatedClient(
    http_client=http_client,
    authenticator=authenticator
)

# Automatically handles 401/403 errors with re-authentication
response = await auth_client.with_retry(
    lambda: portfolio_fetcher.get_positions()
)
```

## Market Data

### Get Markets

```python
from limitless_sdk.markets import MarketFetcher

market_fetcher = MarketFetcher(http_client)

# Get all markets (paginated)
markets = await market_fetcher.get_markets(page=1, limit=50)
print(f"Total: {markets['totalCount']}")
print(f"Markets: {len(markets['data'])}")

# Get specific market (automatically caches venue data)
market = await market_fetcher.get_market("market-slug")
print(f"Title: {market.title}")
print(f"YES Token: {market.tokens.yes}")
print(f"NO Token: {market.tokens.no}")

# Venue data is now cached for efficient order creation
# Includes: exchange address (for signing) and adapter address (for NegRisk approvals)
```

### Get Orderbook

```python
orderbook = await market_fetcher.get_orderbook("market-slug")

# Access bids/asks
for order in orderbook.get('orders', []):
    print(f"Price: {order['price']}, Size: {order['size']}")
```

## Token Approvals

**Important**: Before placing orders, you must approve tokens for the exchange contracts. This is a **one-time setup** per wallet.

### Required Approvals

**CLOB Markets:**
- **BUY orders**: Approve USDC → `market.venue.exchange`
- **SELL orders**: Approve Conditional Tokens → `market.venue.exchange`

**NegRisk Markets:**
- **BUY orders**: Approve USDC → `market.venue.exchange`
- **SELL orders**: Approve Conditional Tokens → **both** `market.venue.exchange` AND `market.venue.adapter`

### Quick Setup

Run the approval setup script:

```bash
# Configure your wallet in .env
python examples/00_setup_approvals.py
```

### Manual Approval Example

```python
from web3 import Web3
from eth_account import Account
from limitless_sdk.markets import MarketFetcher
from limitless_sdk.utils.constants import get_contract_address

# 1. Fetch market to get venue addresses
market = await market_fetcher.get_market('market-slug')

# 2. Initialize Web3 and wallet
w3 = Web3(Web3.HTTPProvider('https://mainnet.base.org'))
account = Account.from_key(private_key)

# 3. Get contract addresses
usdc_address = get_contract_address("USDC", 8453)
ctf_address = get_contract_address("CTF", 8453)

# 4. Create contract instances
usdc = w3.eth.contract(address=usdc_address, abi=ERC20_APPROVE_ABI)
ctf = w3.eth.contract(address=ctf_address, abi=ERC1155_APPROVAL_ABI)

# 5. Approve USDC for BUY orders
max_uint256 = 2**256 - 1
tx = usdc.functions.approve(venue.exchange, max_uint256).build_transaction({...})
signed_tx = account.sign_transaction(tx)
w3.eth.send_raw_transaction(signed_tx.raw_transaction)

# 6. Approve CT for SELL orders
tx = ctf.functions.setApprovalForAll(venue.exchange, True).build_transaction({...})
signed_tx = account.sign_transaction(tx)
w3.eth.send_raw_transaction(signed_tx.raw_transaction)

# 7. For NegRisk SELL orders, also approve adapter
if market.neg_risk_request_id:
    tx = ctf.functions.setApprovalForAll(venue.adapter, True).build_transaction({...})
    signed_tx = account.sign_transaction(tx)
    w3.eth.send_raw_transaction(signed_tx.raw_transaction)
```

For complete examples with proper ABIs and transaction handling, see [examples/00_setup_approvals.py](./examples/00_setup_approvals.py).

## Order Management

The SDK supports two order types:

- **GTC (Good-Till-Cancelled)**: Uses `price` + `size` parameters
- **FOK (Fill-Or-Kill)**: Uses `maker_amount` (total USDC to spend/receive)

### Create GTC Orders

```python
from limitless_sdk.orders import OrderClient
from limitless_sdk.types import Side, OrderType, UserData

# Setup order client
user_data = UserData(
    user_id=auth_result.profile.id,
    fee_rate_bps=auth_result.profile.fee_rate_bps
)

order_client = OrderClient(
    http_client=http_client,
    wallet=account,
    user_data=user_data
)

# Get token ID from market
token_id = str(market.tokens.yes)  # or market.tokens.no

# Create BUY GTC order
order = await order_client.create_order(
    token_id=token_id,
    price=0.50,      # Minimum acceptable price
    size=5.0,        # Number of shares
    side=Side.BUY,
    order_type=OrderType.GTC,
    market_slug=market.slug
)

print(f"Order ID: {order.order.id}")
print(f"Status: {order.order.status}")
```

### Create FOK Orders

```python
# FOK orders use maker_amount instead of price/size
order = await order_client.create_order(
    token_id=token_id,
    maker_amount=10.0,   # Total USDC to spend
    side=Side.BUY,
    order_type=OrderType.FOK,
    market_slug=market.slug
)

# Check if filled
if order.maker_matches and len(order.maker_matches) > 0:
    print(f"FILLED: {len(order.maker_matches)} matches")
else:
    print("NOT FILLED (cancelled)")
```

### Cancel Orders

```python
# Cancel single order by ID
await order_client.cancel(order_id)

# Cancel all orders for a market
await order_client.cancel_all(market_slug)
```

## Portfolio

### Get Positions

```python
from limitless_sdk.portfolio import PortfolioFetcher

portfolio_fetcher = PortfolioFetcher(http_client)

# Get positions
positions = await portfolio_fetcher.get_positions()

# Access CLOB positions
clob_positions = positions['clob']
for position in clob_positions:
    print(f"Market: {position['market']['title']}")
    print(f"Size: {position['size']}")

# Access points
print(f"Points: {positions['accumulativePoints']}")
```

## WebSocket Support

Subscribe to real-time orderbook updates:

```python
from limitless_sdk.websocket import WebSocketClient, WebSocketConfig

# Setup WebSocket
config = WebSocketConfig(
    url="wss://ws.limitless.exchange",
    auto_reconnect=True,
    reconnect_delay=1.0
)
ws_client = WebSocketClient(config=config)

# Event handlers
@ws_client.on('connect')
async def on_connect():
    print("Connected")

@ws_client.on('orderbookUpdate')
async def on_orderbook_update(data):
    orderbook = data.get('orderbook', data)
    best_bid = orderbook['bids'][0]['price']
    best_ask = orderbook['asks'][0]['price']
    print(f"Bid: {best_bid:.4f} | Ask: {best_ask:.4f}")

# Connect and subscribe
await ws_client.connect()
await ws_client.subscribe('subscribe_market_prices', {'marketSlugs': [market_slug]})
```

## Error Handling

The SDK provides `APIError` for all API-related errors:

```python
from limitless_sdk.api import APIError

try:
    order = await order_client.create_order(...)
except APIError as e:
    print(f"Status: {e.status_code}")
    print(f"Error: {e}")  # Prints raw API response JSON
```

### Retry Mechanism

Use the `@retry_on_errors` decorator for custom retry logic:

```python
from limitless_sdk.api import retry_on_errors

@retry_on_errors(
    status_codes={500, 429},
    max_retries=3,
    delays=[1, 2, 3],
    on_retry=lambda attempt, error, delay: print(f"Retry {attempt+1}/3")
)
async def fetch_data():
    return await http_client.get("/endpoint")
```

### Logging

Enable debug logging to see request headers and details:

```python
from limitless_sdk.types import ConsoleLogger, LogLevel

logger = ConsoleLogger(level=LogLevel.DEBUG)
http_client = HttpClient(base_url="...", logger=logger)
```

## Architecture

The SDK is organized into modular components:

### Core Components

- **`HttpClient`**: Low-level HTTP client with retry logic and custom headers
- **`MessageSigner`**: EIP-712 message signing for authentication
- **`Authenticator`**: Handles EOA authentication flow
- **`AuthenticatedClient`**: Auto-retry wrapper with session management

### Domain Components

- **`MarketFetcher`**: Market data retrieval (markets, orderbooks)
- **`OrderClient`**: Order creation/cancellation with automatic signing
- **`PortfolioFetcher`**: Portfolio and positions data
- **`WebSocketClient`**: Real-time orderbook updates

### Type System

The SDK uses Pydantic models for type safety:

- **`LoginOptions`**: Authentication configuration
- **`UserData`**: User profile data
- **`Side`**: `BUY` / `SELL` enum
- **`OrderType`**: `GTC` / `FOK` enum
- **`LogLevel`**: `DEBUG` / `INFO` / `WARN` / `ERROR` enum

## Examples

See the [`examples/`](./examples) directory for complete working examples:

- **`01_authentication.py`** - EOA authentication with custom headers
- **`02_create_buy_gtc_order.py`** - Create BUY GTC order
- **`03_cancel_gtc_order.py`** - Cancel orders (single or all)
- **`04_create_sell_gtc_order.py`** - Create SELL GTC order
- **`05_create_buy_fok_order.py`** - Create BUY FOK order
- **`06_create_sell_fok_order.py`** - Create SELL FOK order
- **`06_retry_handling.py`** - Custom retry logic with `@retry_on_errors`
- **`07_auto_retry_second_sample.py`** - Auto-retry with `AuthenticatedClient`
- **`08_websocket_events.py`** - Real-time orderbook updates

## Development

### Setup

```bash
git clone https://github.com/limitless-labs-group/limitless-exchange-ts-sdk.git
cd limitless-sdk
pip install -e ".[dev]"
```

### Testing

```bash
pytest
```

### Linting

```bash
ruff check .
mypy limitless_sdk/
```

## License

MIT License - see LICENSE file for details.

## Support

For questions or issues:

- GitHub Issues: [Create an issue](https://github.com/your-org/limitless-sdk/issues)
- Email: support@limitless.ai

## Key Features

### Venue Caching System

The SDK automatically caches venue data (exchange and adapter contract addresses) to optimize performance when creating multiple orders for the same market.

**How it works**:

```python
# Fetch market once
market_fetcher = MarketFetcher(http_client)
market = await market_fetcher.get_market("bitcoin-2024")

# Venue data is now cached automatically
# {
#   exchange: "0xa4409D988CA2218d956BeEFD3874100F444f0DC3",  # for order signing
#   adapter: "0x5a38afc17F7E97ad8d6C547ddb837E40B4aEDfC6"    # for NegRisk approvals
# }

# Create multiple orders without additional API calls
order_client = OrderClient(http_client, wallet, user_data)

# Venue is fetched from cache (no API call)
order1 = await order_client.create_order(
    token_id=str(market.tokens.yes),
    price=0.50,
    size=5.0,
    side=Side.BUY,
    order_type=OrderType.GTC,
    market_slug=market.slug
)

# Still using cached venue data
order2 = await order_client.create_order(
    token_id=str(market.tokens.no),
    price=0.30,
    size=10.0,
    side=Side.BUY,
    order_type=OrderType.GTC,
    market_slug=market.slug
)
```

**Performance benefits**:
- Eliminates redundant `/venues/:slug` API calls
- Faster order creation (cache hit vs network request)
- Reduced API rate limit usage

**Debug logging**: Enable debug mode to see venue cache operations:

```python
logger = ConsoleLogger(level=LogLevel.DEBUG)
http_client = HttpClient(base_url="...", logger=logger)

# You'll see:
# [Limitless SDK] Venue cached for order signing {
#   slug: 'bitcoin-2024',
#   exchange: '0xa4409D988CA2218d956BeEFD3874100F444f0DC3',
#   adapter: '0x5a38afc17F7E97ad8d6C547ddb837E40B4aEDfC6',
#   cacheSize: 1
# }
# [Limitless SDK] Venue cache hit { slug: 'bitcoin-2024', exchange: '0xa4...' }
```

### Token ID Extraction

CLOB markets use a tokens object for YES/NO positions:

```python
# Get YES token ID
token_id = str(market.tokens.yes)

# Get NO token ID
token_id = str(market.tokens.no)
```

### Raw API Responses

The SDK returns raw API responses without heavy parsing, allowing direct access to all fields:

```python
# Markets response
markets = await market_fetcher.get_markets()
total = markets['totalCount']
data = markets['data']

# Positions response
positions = await portfolio_fetcher.get_positions()
clob = positions['clob']
points = positions['accumulativePoints']
```

### Order Type Parameters

- **GTC orders**: `price` + `size`

  ```python
  price=0.50,  # Minimum acceptable price
  size=5.0     # Number of shares
  ```

- **FOK orders**: `maker_amount`
  ```python
  maker_amount=10.0  # Total USDC to spend/receive
  ```

## Changelog

### v3.0.1

- **Venue Caching System**: Automatic venue data caching for improved performance
  - `MarketFetcher` now caches venue data (exchange, adapter addresses) per market
  - Eliminates redundant API calls when creating multiple orders for the same market
  - Venue cache automatically populated via `get_market()` calls
  - Performance optimization: fetch market once, reuse venue data for all orders
- **Enhanced Debug Logging**: Improved observability for venue operations
  - `get_market()`: Logs venue cache status with exchange/adapter addresses and cache size
  - `get_venue()`: Logs cache hits/misses for performance monitoring
  - Warning logs when market doesn't have venue data
  - Debug mode shows complete venue lifecycle (fetch → cache → reuse)
- **Documentation**: Comprehensive venue system documentation
  - New venue system section in trading guide explaining exchange/adapter roles
  - Best practices guide for venue caching patterns
  - Token approval requirements per market type (CLOB vs NegRisk)
  - Complete examples showing optimal marketFetcher sharing patterns

### v0.3.0

- **Architecture**: Refactored to modular component structure
  - `HttpClient` with connection pooling via aiohttp
  - `OrderClient` for order management with automatic signing
  - `MarketFetcher` for market data operations
  - `PortfolioFetcher` for portfolio/positions queries
- **WebSocket Support**: Real-time orderbook updates via `WebSocketClient`
  - Event-based subscription system with decorators
  - Auto-reconnect functionality with configurable delays
  - Typed event handlers for orderbook updates
- **Authentication**: Enhanced authentication system
  - `MessageSigner` for EIP-712 message signing
  - `Authenticator` for EOA authentication flow
  - `AuthenticatedClient` wrapper for automatic session re-authentication
- **HTTP Client**: Structured HTTP client with advanced features
  - Connection pooling and session management
  - Global and per-request custom headers
  - Configurable logging with `ConsoleLogger` and log levels
  - Retry decorator (`@retry_on_errors`) with customizable delays
- **Order System**: Improved order handling
  - Support for GTC (Good-Till-Cancelled) orders with `price` + `size`
  - Support for FOK (Fill-Or-Kill) orders with `maker_amount`
  - Automatic order signing and submission
  - Order cancellation (single and batch)
- **Documentation**: Comprehensive examples directory with 9 working examples
- **README**: Updated to reflect actual implementation patterns

### v0.2.0

- Added `additional_headers` parameter to `HttpClient`
- Global and per-request header configuration
- `AuthenticatedClient` for auto-retry on session expiration
- WebSocket support for real-time updates
- Retry decorator (`@retry_on_errors`)
- Comprehensive examples directory
- Fixed license configuration in pyproject.toml

### v0.1.0

- Initial release
- EOA authentication with EIP-712 signing
- Market data access
- GTC and FOK order support
- Portfolio tracking
