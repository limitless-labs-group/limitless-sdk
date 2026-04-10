# API Token v3 Examples

Partner-facing examples for:
- `GET /auth/api-tokens/capabilities`
- `POST /auth/api-tokens/derive`
- `GET /auth/api-tokens`
- `DELETE /auth/api-tokens/:tokenId`
- `POST /profiles/partner-accounts`
- delegated `POST /orders` (`GTC` with optional `post_only`)
- delegated `POST /orders` with `FOK`
- delegated cancel by id / cancel all
- WebSocket auth with HMAC-scoped tokens

## Required env

```bash
export LIMITLESS_IDENTITY_TOKEN="..."
export MARKET_SLUG="your-market-slug"
```

Optional overrides:

```bash
export LIMITLESS_API_URL="https://dev4.api.limitless-operations.xyz"
export LIMITLESS_DELEGATED_ACCOUNT_READY_DELAY_MS=10000
export LIMITLESS_PLACE_DELEGATED_ORDER=1
export LIMITLESS_REVOKE_DERIVED_TOKEN=1
export LIMITLESS_HTTP_TRACE=1
```

## Run

```bash
python examples/api_key_v3/api_tokens.py
python examples/api_key_v3/partner_account.py
python examples/api_key_v3/delegated_order.py
python examples/api_key_v3/delegated_fok_order.py
python examples/api_key_v3/e2e_flow.py
python examples/api_key_v3/websocket_hmac.py
```

## Notes

- The HMAC-scoped client signs request headers for you once you configure `HMACCredentials`.
- Delegated server-wallet accounts must be funded before the first delegated trade.
- New server wallets may need a short backend allowance-provisioning delay before trading succeeds.
- In partner-account EOA mode, the wallet you prove with `x-account` / `x-signature` is the child account being linked. It must be different from the parent partner profile account.
