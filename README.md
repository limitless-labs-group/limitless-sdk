# Limitless Exchange Python SDK

A minimalistic, async Python SDK for interacting with the Limitless Exchange API.

## Features

- 🔐 **API Key authentication** - Simple and secure authentication with API keys
- 📈 **Market data access** - Markets, orderbooks, and historical data
- 📋 **Order management** - GTC and FOK orders with automatic signing
- 💼 **Portfolio tracking** - Positions and user history
- 🔄 **Automatic retries** - Configurable retry logic with error handling
- 🌐 **WebSocket support** - Real-time orderbook updates
- 🛡️ **Custom headers** - Global and per-request header configuration
- ⚡ **Async/await support** - Modern async Python with aiohttp
- 🚀 **Venue caching** - Automatic contract address caching for optimized order creation

## ⚠️ Disclaimer

**USE AT YOUR OWN RISK**

This SDK is provided "as-is" without any warranties or guarantees. Trading on prediction markets involves financial risk. By using this SDK, you acknowledge that:

- You are responsible for testing the SDK thoroughly before using it in production
- The SDK authors are not liable for any financial losses or damages
- You should review and understand the code before executing any trades
- It is recommended to test all functionality on testnet or with small amounts first
- The SDK may contain bugs or unexpected behavior despite best efforts

**Feedback Welcome**: We encourage you to report any bugs, suggest improvements, or contribute to the project. Please submit issues or pull requests on our GitHub repository.

## 🌍 Geographic Restrictions

**Important**: Limitless restricts order placement from US locations due to regulatory requirements and compliance with international sanctions. Before placing orders, builders should verify their location complies with applicable regulations.

## Installation

```bash
pip install limitless-sdk
```

## Quick Start

```python
import asyncio
import os
from limitless_sdk.api import HttpClient
from limitless_sdk.markets import MarketFetcher
from limitless_sdk.portfolio import PortfolioFetcher

async def main():
    # Setup - API key automatically loaded from LIMITLESS_API_KEY env variable
    http_client = HttpClient(base_url="https://api.limitless.exchange")

    try:
        # Get markets
        market_fetcher = MarketFetcher(http_client)
        markets = await market_fetcher.get_active_markets()
        print(f"Found {markets.total_markets_count} markets")

        # Fetch specific market (caches venue data for orders)
        market = await market_fetcher.get_market("bitcoin-2024")
        print(f"Market: {market.title}")

        # Get positions (requires authentication)
        portfolio_fetcher = PortfolioFetcher(http_client)
        positions = await portfolio_fetcher.get_positions()
        print(f"CLOB positions: {len(positions['clob'])}")

    finally:
        await http_client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## Authentication

The SDK uses API keys for authentication. API keys can be obtained from your Limitless Exchange account settings.

### Basic Authentication

```python
import os
from limitless_sdk.api import HttpClient

# Option 1: Automatic from environment variable (recommended)
# Set LIMITLESS_API_KEY in your .env file or environment
http_client = HttpClient()

# Option 2: Explicit API key
http_client = HttpClient(
    api_key=os.getenv("LIMITLESS_API_KEY")
)

# Option 3: Custom base URL (for dev/staging)
http_client = HttpClient(
    base_url="https://staging.api.limitless.exchange",
    api_key="sk_test_..."
)

# All requests automatically include X-API-Key header
```

### Environment Variables

Create a `.env` file in your project root:

```bash
# Required for authenticated endpoints
LIMITLESS_API_KEY=sk_live_your_api_key_here

# Optional: Custom API URL (defaults to production)
# LIMITLESS_API_URL=https://api.limitless.exchange
```

### Custom HTTP Headers

You can configure custom headers globally (applied to ALL requests) or per-request:

```python
# Global headers (applied to all requests)
http_client = HttpClient(
    additional_headers={
        "X-Custom-Header": "value",
        "X-API-Version": "v1"
    }
)

# Per-request headers (request ID, tracing, etc.)
response = await http_client.get("/endpoint", headers={"X-Request-ID": "123"})
```

## Market Data

### Get Markets

```python
from limitless_sdk.markets import MarketFetcher

market_fetcher = MarketFetcher(http_client)

# Get active markets (paginated)
markets = await market_fetcher.get_active_markets({"page": 1, "limit": 50})
print(f"Total: {markets.total_markets_count}")
print(f"Markets: {len(markets.data)}")

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
from limitless_sdk.types import Side, OrderType

# Setup order client (userData fetched automatically from profile)
order_client = OrderClient(
    http_client=http_client,
    wallet=account,
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

FOK (Fill-Or-Kill) orders either execute immediately and completely or are cancelled. They use `maker_amount` instead of `price`/`size` parameters.

**Parameter Semantics**:

- **BUY orders**: `maker_amount` = total USDC to spend (e.g., 10.0 = $10 USDC)
- **SELL orders**: `maker_amount` = number of shares to sell (e.g., 18.64 shares)

```python
# FOK BUY order - spend $10 USDC
order = await order_client.create_order(
    token_id=token_id,
    maker_amount=10.0,   # Spend $10 USDC
    side=Side.BUY,
    order_type=OrderType.FOK,
    market_slug=market.slug
)

# FOK SELL order - sell 18.64 shares
order = await order_client.create_order(
    token_id=token_id,
    maker_amount=18.64,  # Sell 18.64 shares
    side=Side.SELL,
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

- **`HttpClient`**: Low-level HTTP client with API key authentication and retry logic
- **`OrderSigner`**: EIP-712 message signing for order creation
- **`RetryableClient`**: Auto-retry wrapper with configurable retry strategies

### Domain Components

- **`MarketFetcher`**: Market data retrieval (markets, orderbooks)
- **`OrderClient`**: Order creation/cancellation with automatic signing
- **`PortfolioFetcher`**: Portfolio and positions data
- **`WebSocketClient`**: Real-time orderbook updates

### Type System

The SDK uses Pydantic models for type safety:

- **`UserProfile`**: User account information
- **`Side`**: `BUY` / `SELL` enum
- **`OrderType`**: `GTC` / `FOK` enum
- **`LogLevel`**: `DEBUG` / `INFO` / `WARN` / `ERROR` enum
- **`Market`**: Market metadata and configuration

## Examples

See the [`examples/`](./examples) directory for complete working examples:

- **`01_authentication.py`** - API key authentication with portfolio data
- **`02_create_buy_gtc_order.py`** - Create BUY GTC order
- **`03_cancel_gtc_order.py`** - Cancel orders (single or all)
- **`04_create_sell_gtc_order.py`** - Create SELL GTC order
- **`05_create_buy_fok_order.py`** - Create BUY FOK order
- **`06_create_sell_fok_order.py`** - Create SELL FOK order
- **`06_retry_handling.py`** - Custom retry logic with `@retry_on_errors`
- **`07_auto_retry_second_sample.py`** - Auto-retry with `RetryableClient`
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

# Create order client (userData fetched automatically from profile on first order)
order_client = OrderClient(http_client, wallet)

# Venue is fetched from cache (no API call)
# User data is fetched automatically on first order creation
order1 = await order_client.create_order(
    token_id=str(market.tokens.yes),
    price=0.50,
    size=5.0,
    side=Side.BUY,
    order_type=OrderType.GTC,
    market_slug=market.slug
)

# Still using cached venue data and user data
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

- **GTC orders**: Use `price` + `size` parameters

  ```python
  price=0.50,  # Minimum acceptable price (0-1 range)
  size=5.0     # Number of shares to buy/sell
  ```

- **FOK orders**: Use `maker_amount` parameter (semantics differ by side)

  ```python
  # BUY: Total USDC to spend
  maker_amount=10.0  # Spend $10 USDC to buy shares

  # SELL: Number of shares to sell
  maker_amount=18.64 # Sell 18.64 shares for USDC
  ```

## Changelog

### v1.0.0

**Release Date**: January 2026

This is the first stable, production-ready release of the Limitless Exchange Python SDK, designated as a Long-Term Support (LTS) version. This release consolidates all features and improvements from pre-release versions into a stable, well-documented, and thoroughly tested SDK.

#### Core Features

- **🔐 Authentication & Security**

  - API key authentication with X-API-Key header
  - EIP-712 message signing for order creation
  - `OrderSigner` for cryptographic order signing operations
  - `AuthenticationError` for authentication failure handling
  - Secure API key management from environment variables

- **📊 Market Data Access**

  - `MarketFetcher` with intelligent venue caching system
  - Active markets retrieval with pagination and sorting
  - Market-specific data fetching (slug-based)
  - Real-time orderbook data
  - Automatic venue data caching for performance optimization
  - Cache-aware market operations (eliminates redundant API calls)

- **📋 Order Management**

  - `OrderClient` for comprehensive order operations
  - **GTC Orders** (Good-Till-Cancelled): `price` + `size` parameters
  - **FOK Orders** (Fill-Or-Kill): `maker_amount` parameter
    - BUY: maker_amount = total USDC to spend
    - SELL: maker_amount = number of shares to sell
  - Automatic EIP-712 order signing with venue.exchange integration
  - Dynamic venue resolution from cache or API
  - Order cancellation (single order and batch operations)
  - Maker match tracking and order status monitoring

- **💼 Portfolio Management**

  - `PortfolioFetcher` for position tracking
  - CLOB position data retrieval
  - User history access
  - Accumulative points tracking
  - Portfolio-wide analytics

- **🌐 WebSocket Support**

  - `WebSocketClient` for real-time orderbook updates
  - Event-based subscription system with decorators
  - Auto-reconnect functionality with configurable delays
  - Typed event handlers for orderbook updates
  - Connection lifecycle management

- **🔄 Retry & Error Handling**

  - `@retry_on_errors` decorator with customizable retry logic
  - `RetryableClient` for automatic retry on transient failures
  - Configurable delays and maximum retry attempts
  - Status code-based retry strategies
  - Comprehensive `APIError` exception hierarchy (`AuthenticationError`, `RateLimitError`, `ValidationError`)

- **📝 Logging & Debugging**

  - `ConsoleLogger` with configurable log levels (DEBUG, INFO, WARN, ERROR)
  - Enhanced debug logging for venue operations
  - Venue cache monitoring (hits/misses)
  - Request/response logging with header visibility
  - Performance tracking and observability

- **🛡️ Token Approval System**
  - Complete token approval setup guide
  - CLOB market approval workflows
  - NegRisk market dual-approval requirements
  - Web3 integration examples
  - ERC-20 (USDC) and ERC-1155 (Conditional Tokens) support

#### Performance & Optimization

- **Venue Caching**: Automatic venue data caching eliminates redundant API calls
- **Connection Pooling**: Efficient HTTP client with aiohttp connection pooling
- **Async/Await**: Full async support for optimal performance
- **Session Reuse**: Persistent HTTP sessions for improved performance
- **Custom Headers**: Global and per-request header configuration

#### Documentation & Examples

- **Comprehensive README**: 650+ lines covering all features
- **9 Working Examples**:

  1. `00_setup_approvals.py` - Token approval setup
  2. `01_authentication.py` - API key authentication with portfolio data
  3. `02_create_buy_gtc_order.py` - GTC BUY orders
  4. `03_cancel_gtc_order.py` - Order cancellation
  5. `04_create_sell_gtc_order.py` - GTC SELL orders
  6. `05_create_buy_fok_order.py` - FOK BUY orders
  7. `06_create_sell_fok_order.py` - FOK SELL orders
  8. `06_retry_handling.py` - Custom retry logic
  9. `07_auto_retry_second_sample.py` - Auto-retry patterns with RetryableClient
  10. `08_websocket_events.py` - Real-time WebSocket events

- **Documentation Quality Improvements**:
  - Accurate FOK order parameter documentation (BUY vs SELL semantics)
  - Clear GTC order price parameter explanations
  - Comprehensive venue system documentation
  - Token approval requirements by market type
  - Best practices for venue caching and performance

#### Architecture

- **Modular Design**: Clean separation of concerns with focused components
- **Type Safety**: Full Pydantic model integration for type validation
- **Extensibility**: Easy to extend with custom authentication or signing logic
- **Standards Compliance**: Follows Python async best practices

#### Quality Assurance

- Production-ready code quality
- Comprehensive error handling
- Well-documented public APIs
- Consistent coding patterns
- Validated against live Base mainnet

#### Breaking Changes from Pre-Release

None - this is the first stable release. All pre-release versions (v0.x) were development versions leading to this LTS release.

---

### Pre-Release Versions

The following versions were development releases leading to v1.0.0:

#### v0.3.1 (Pre-release)

- Venue caching system implementation
- Enhanced debug logging
- Venue system documentation

#### v0.3.0 (Pre-release)

- Modular architecture refactor
- WebSocket support
- Enhanced authentication system
- HTTP client improvements
- Order system enhancements

#### v0.2.0 (Pre-release)

- Added `additional_headers` parameter to `HttpClient`
- Global and per-request header configuration
- `RetryableClient` for automatic retry on transient failures
- WebSocket support for real-time updates
- Retry decorator (`@retry_on_errors`)
- Comprehensive examples directory
- Fixed license configuration in pyproject.toml

#### v0.1.0 (Pre-release)

- Initial release
- API key authentication with X-API-Key header
- EIP-712 signing for order creation
- Market data access
- GTC and FOK order support
- Portfolio tracking

---

## LTS Support Policy

**v1.0.0 LTS** will receive:

- Security updates and critical bug fixes
- Compatibility maintenance with Limitless Exchange API
- Community support and issue resolution
- Documentation updates and improvements

For production deployments, we recommend using the LTS version for stability and long-term support.
