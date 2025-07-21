# Limitless Exchange Python SDK

A clean, async Python SDK for interacting with the Limitless Exchange API.

## Features

- 🔐 **Ethereum wallet authentication** - Sign in with your private key
- 📈 **Market data access** - Get markets, prices, and historical data  
- 📋 **Order management** - Place, cancel, and manage orders
- 💼 **Portfolio tracking** - View positions and trading history
- 🔄 **Automatic retries** - Built-in retry logic for rate limits
- 🛡️ **Type safety** - Full Pydantic models for request/response validation
- ⚡ **Async/await support** - Modern async Python with aiohttp

## Installation

```bash
pip install limitless-sdk
```

Or install from source:

```bash
git clone https://github.com/your-org/limitless-sdk.git
cd limitless-sdk
pip install -e .
```

## Quick Start

```python
import asyncio
from limitless_sdk import LimitlessClient

async def main():
    # Initialize client with your private key
    async with LimitlessClient(private_key="your_private_key_here") as client:
        # Login
        await client.login()
        
        # Get active markets
        markets = await client.get_active_markets()
        print(f"Found {len(markets)} markets")
        
        # Get market details
        market = await client.get_market("market-slug")
        
        # Get orderbook
        orderbook = await client.get_orderbook("market-slug")
        
        # Get your positions
        positions = await client.get_positions()

if __name__ == "__main__":
    asyncio.run(main())
```

## Authentication

The SDK requires an Ethereum private key for authentication. Pass it directly to the client constructor:

```python
from limitless_sdk import LimitlessClient

# Initialize with your private key
client = LimitlessClient(private_key="0x1234567890abcdef...")

# For applications, you might load from environment variables
import os
client = LimitlessClient(private_key=os.getenv("PRIVATE_KEY"))
```

### Additional Headers

You can pass additional HTTP headers that will be included in all API requests. This is useful for rate limiting bypass headers or other custom authentication:

```python
# Initialize with additional headers (e.g., for rate limiting bypass)
additional_headers = {
    "x-rate-limit-bypass": "your-secret-token",
    "x-custom-header": "custom-value"
}

client = LimitlessClient(
    private_key="your_private_key_here",
    additional_headers=additional_headers
)
```

**Note:** Additional headers are included in all HTTP requests made by the SDK, including authentication, market data, and trading operations.

## Market Data

### Get Markets

```python
# Get all markets with pagination
markets = await client.get_active_markets(page=1, limit=10)

# Get all active markets (handles pagination automatically)
all_markets = await client.get_all_active_markets()

# Get specific market
market = await client.get_market("market-slug-or-address")
```

### Get Historical Data

```python
# Get historical prices
data, interval = await client.get_historical_prices("market-slug")
print(f"Data interval: {interval}")
print(f"Price points: {len(data['prices'])}")
```

### Get Orderbook

```python
orderbook = await client.get_orderbook("market-slug")
print(f"Orders: {len(orderbook['orders'])}")
```

## Order Management

### Place Orders

```python
from limitless_sdk import Order, CreateOrderDto, OrderType, OrderSide
import time

# Create order
order = Order(
    salt=int(time.time()),
    maker="0x...",  # Your wallet address
    signer="0x...",  # Your wallet address
    token_id="token123",
    maker_amount="1000000",  # Amount in wei
    taker_amount="1000000",  # Amount in wei
    price="0.5",
    fee_rate_bps=30,  # 0.3% fee
    side=OrderSide.BUY,
    signature="0x...",  # Order signature
)

create_order_dto = CreateOrderDto(
    order=order,
    order_type=OrderType.LIMIT,
    market_slug="market-slug"
)

# Place the order
result = await client.place_order(create_order_dto)
```

### Cancel Orders

```python
from limitless_sdk import CancelOrderDto, DeleteOrderBatchDto, MarketSlugValidator

# Cancel single order
cancel_dto = CancelOrderDto(order_id="order-id")
await client.cancel_order(cancel_dto)

# Cancel multiple orders
batch_dto = DeleteOrderBatchDto(order_ids=["order1", "order2"])
await client.cancel_order_batch(batch_dto)

# Cancel all orders for a market
market_validator = MarketSlugValidator(slug="market-slug")
await client.cancel_all_orders(market_validator)
```

### Get User Orders

```python
# Get your orders for a specific market
orders = await client.get_user_orders("market-slug")
```

## Portfolio

### Get Positions

```python
positions = await client.get_positions()
for position in positions:
    print(f"Market: {position['market']['title']}")
    print(f"Size: {position['size']}")
```

### Get Trading History

```python
# Get paginated history
history = await client.get_user_history(page=1, limit=50)
print(f"Total entries: {history['totalCount']}")

for entry in history['data']:
    print(f"Type: {entry['type']}")
    print(f"Amount: {entry['amount']}")
```

## Error Handling

The SDK includes custom exceptions for different error types:

```python
from limitless_sdk import LimitlessAPIError, RateLimitError, AuthenticationError

try:
    await client.get_markets()
except RateLimitError as e:
    print(f"Rate limited: {e}")
    # SDK automatically retries rate limits
except AuthenticationError as e:
    print(f"Auth failed: {e}")
except LimitlessAPIError as e:
    print(f"API error {e.status_code}: {e}")
```

## Rate Limiting

The SDK automatically handles rate limits with exponential backoff:

- **Automatic retries** for 429 (Too Many Requests) responses
- **Configurable retry delays** (default: 5s, 10s)
- **Max retry attempts** (default: 2)



### Logging

Enable debug logging to see API requests:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Models

The SDK uses Pydantic models for type safety:

### Order Models

- `Order` - Order details for creation
- `CreateOrderDto` - Order creation request
- `CancelOrderDto` - Order cancellation request
- `DeleteOrderBatchDto` - Batch order cancellation
- `MarketSlugValidator` - Market slug validation

### Enums

- `OrderSide.BUY` / `OrderSide.SELL`
- `OrderType.LIMIT` / `OrderType.MARKET`

## Development

### Setup

```bash
git clone https://github.com/your-org/limitless-sdk.git
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

## Changelog

### v0.2.0

- **New Feature**: Added `additional_headers` parameter to `LimitlessClient`
  - Allows passing custom headers (e.g., rate limiting bypass tokens)
  - Headers are included in all API requests automatically
  - Maintains backward compatibility
- Fixed license configuration in pyproject.toml
- Enhanced test coverage for header functionality

### v0.1.0

- Initial release
- Market data access
- Order management  
- Portfolio tracking
- Automatic rate limit handling
