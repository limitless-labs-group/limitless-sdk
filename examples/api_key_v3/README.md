# API Token v3 Examples

Partner-facing examples for:
- `GET /auth/api-tokens/capabilities`
- `POST /auth/api-tokens/derive`
- `GET /auth/api-tokens`
- `DELETE /auth/api-tokens/:tokenId`
- `POST /profiles/partner-accounts`
- `GET /profiles/partner-accounts/:profileId/allowances`
- `POST /profiles/partner-accounts/:profileId/allowances/retry`
- delegated `POST /orders` (`GTC` with optional `post_only`)
- delegated `POST /orders` with `FOK`
- delegated `POST /orders` with `FAK`
- `POST /portfolio/redeem`
- `POST /portfolio/withdraw`
- delegated cancel by id / cancel all
- WebSocket auth with HMAC-scoped tokens

## Required env

```bash
export LIMITLESS_IDENTITY_TOKEN="..."
export LIMITLESS_API_TOKEN_ID="..."
export LIMITLESS_API_TOKEN_SECRET="..."
export MARKET_SLUG="your-market-slug"
```

Optional overrides:

```bash
export LIMITLESS_API_URL="https://dev4.api.limitless-operations.xyz"
export LIMITLESS_DELEGATED_ACCOUNT_READY_DELAY_MS=10000
export LIMITLESS_PLACE_DELEGATED_ORDER=1
export LIMITLESS_REVOKE_DERIVED_TOKEN=1
export LIMITLESS_HTTP_TRACE=1
export LIMITLESS_SKIP_WITHDRAW=1
export LIMITLESS_SKIP_ALLOWANCE_RETRY=1
export LIMITLESS_PARTNER_ACCOUNT_PROFILE_ID=
export LIMITLESS_WITHDRAW_AMOUNT=
export LIMITLESS_WITHDRAW_DESTINATION=
export LIMITLESS_WITHDRAW_TOKEN=
export LIMITLESS_ON_BEHALF_OF=
export LIMITLESS_SERVER_WALLET_ACCOUNT=
```

## Run

```bash
python examples/api_key_v3/api_tokens.py
python examples/api_key_v3/partner_account.py
python examples/api_key_v3/partner_account_allowances.py
python examples/api_key_v3/delegated_order.py
python examples/api_key_v3/delegated_fok_order.py
python examples/api_key_v3/server_wallet_redeem_withdraw.py
python examples/api_key_v3/e2e_flow.py
python examples/api_key_v3/websocket_hmac.py
```

## Notes

- The HMAC-scoped client signs request headers for you once you configure `HMACCredentials`.
- Delegated server-wallet accounts must be funded before the first delegated trade.
- New server wallets may need allowance recovery before trading succeeds. Use `client.partner_accounts.check_allowances(profile_id)` and `client.partner_accounts.retry_allowances(profile_id)` for server-wallet child profiles.
- `partner_account_allowances.py` uses only partner HMAC credentials and does not call admin APIs.
- Allowance checks are based on live chain reads. A retry response with submitted targets means that retry request submitted a sponsored transaction or user operation; poll `check_allowances()` again after a short delay.
- Retry `429` responses raise `RateLimitError` and include `retryAfterSeconds` in `error.response_data`; retry `409` responses raise `ConflictError`.
- The server-wallet redeem/withdraw example is only for child accounts created with `create_server_wallet=True`.
- `LIMITLESS_ON_BEHALF_OF` lets the redeem/withdraw example target an existing child profile that already holds resolved positions.
- `LIMITLESS_SKIP_WITHDRAW=1` is the safe default; set it to `0` and provide `LIMITLESS_WITHDRAW_AMOUNT` to run the withdraw step.
- In partner-account EOA mode, the wallet you prove with `x-account` / `x-signature` is the child account being linked. It must be different from the parent partner profile account.
