# Limitless SDK Python Examples

Minimalistic examples demonstrating the Limitless SDK Python client.

## Setup

```bash
pip install limitless-sdk
export LIMITLESS_API_KEY="sk_live_..."  # For authenticated endpoints
export PRIVATE_KEY="0x..."              # For order signing (EIP-712)
export MARKET_SLUG="your-market-slug"   # For order examples
```

## Examples

### [01_authentication.py](./01_authentication.py)
API key authentication with portfolio data access.

```bash
python examples/01_authentication.py
```

### [02_create_buy_gtc_order.py](./02_create_buy_gtc_order.py)
Create BUY GTC (Good-Till-Cancelled) order.

### [03_cancel_gtc_order.py](./03_cancel_gtc_order.py)
Cancel single order by ID or all orders for a market.

### [04_create_sell_gtc_order.py](./04_create_sell_gtc_order.py)
Create SELL GTC order.

### [05_create_buy_fok_order.py](./05_create_buy_fok_order.py)
Create BUY FOK (Fill-Or-Kill) order with `maker_amount`.

### [06_create_sell_fok_order.py](./06_create_sell_fok_order.py)
Create SELL FOK order with `maker_amount`.

### [06_retry_handling.py](./06_retry_handling.py)
Retry mechanism - 3 retries on 404 errors using `@retry_on_errors` decorator.

### [07_auto_retry_second_sample.py](./07_auto_retry_second_sample.py)
RetryableClient pattern for automatic retry on transient failures.

### [08_websocket_events.py](./08_websocket_events.py)
Real-time orderbook updates via WebSocket subscription.

## Key Concepts

**Token ID Extraction:**
```python
# CLOB markets use tokens object
token_id = str(market.tokens.yes)  # or market.tokens.no
```

**Raw API Responses:**
SDK returns raw API responses without parsing:
```python
response = await portfolio_fetcher.get_positions()
clob_positions = response['clob']
points = response['accumulativePoints']
```

**Order Types:**
- **GTC (Good-Till-Cancelled)**: Uses `price` + `size` parameters
- **FOK (Fill-Or-Kill)**: Uses `maker_amount` (total USDC to spend/receive)

**Error Handling:**
```python
from limitless_sdk.api import APIError

try:
    order = await order_client.create_order(...)
except APIError as e:
    print(e)  # Prints raw API response JSON
    print(e.status_code)
```

## Troubleshooting

**PRIVATE_KEY not loading:**
```python
from dotenv import load_dotenv
load_dotenv()
```

**Order creation failures:**
- Verify USDC balance on Base network (Chain ID: 8453)
- Check market liquidity
- Confirm `token_id` from `market.tokens.yes` or `market.tokens.no`
