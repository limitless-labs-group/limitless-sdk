# Changelog

All notable changes to the Limitless Exchange Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0]

### Added

- WebSocket `orderEvent` now models two additional frames on the existing union members:
  - OME `EXECUTION` (FAK/FOK terminal): `OmeOrderEvent.type` gains `"EXECUTION"`, plus a `status` of `"FILLED" | "PARTIALLY_FILLED" | "KILLED"` (present only on `EXECUTION`). Its `eventId` is the string `"terminal:<orderId>"`.
  - Settlement `MATCHED` (pre-settlement per-fill): `SettlementOrderEvent.type` gains `"MATCHED"`, plus `isEstimate: bool` and `token: "YES" | "NO"`. On `MATCHED` the maker side reports a fee of 0 and the taker reports a real estimate.
- The POST /orders response now models the `execution` object (`Execution` / `ExecutionTotalsRaw`), previously dropped. It carries the settlement/fee summary and the taker-delay outcome: `matched`, `settlementStatus` (plain string — known values `UNMATCHED` / `MATCHED` / `MINED` / `CONFIRMED` / `RETRYING` / `FAILED` / `DELAYED`), optional `tradeEventId` / `txHash` / `clientOrderId`, `eligibleAt` (ISO-8601, present only when `settlementStatus == "DELAYED"` — when the order is released to the matching engine), `feeRateBps`, `effectiveFeeBps`, and the raw integer-string `totalsRaw`. Modeled optionally on `OrderResponse` for back-compat. Additive, non-breaking.

### Changed

- **BREAKING (type-only):** `OmeOrderEvent.price` and `OmeOrderEvent.remainingSize` are now typed `float` instead of `str`, and `OmeOrderEvent.eventId` is now `Union[int, str]` instead of `int`. The runtime values never changed — all OME frames have always emitted `price`/`remainingSize` as JSON numbers and the terminal `eventId` as a string; only the static types are corrected. Consumers that parsed these as strings should drop the conversion.
- README, examples docs, package metadata, lockfile, and runtime `__version__` now target `v1.1.0`.

## [1.0.11]

### Added

- Authenticated current-profile lookup via `PortfolioFetcher.get_current_profile()`, which calls `GET /profiles/me`.
- Partner-owned account listing and recovery via `PartnerAccountService.list_accounts()`.
- Public partner account list models:
  - `ListPartnerAccountsParams`
  - `PartnerAccountListItem`
  - `ListPartnerAccountsResponse`
- Focused tests for `/profiles/me` profile reads and HMAC-only partner account listing, filtering, pagination capping, and invalid query params.

### Changed

- Removed unsupported legacy websocket short channel literals and stale typed event exports for unsupported events.
- Added runtime validation so dynamic websocket subscriptions fail fast unless they use a supported backend channel.
- README, examples docs, package metadata, lockfile, and runtime `__version__` now target `v1.0.11`.

## [1.0.10]

### Fixed

- Fixed HMAC WebSocket authentication for Python Socket.IO clients by signing the Engine.IO WebSocket path emitted by `python-engineio` and disabling timestamp cache-buster query parameters.

## [1.0.9]

### Added

- Partner withdrawal-address allowlist helpers:
  - `PartnerAccountService.add_withdrawal_address()`
  - `PartnerAccountService.delete_withdrawal_address()`
- Public withdrawal-address request/response models:
  - `PartnerWithdrawalAddressInput`
  - `PartnerWithdrawalAddressResponse`
- `HttpClient.delete_with_identity()` and `RetryableClient.delete_with_identity()` for identity-token authenticated DELETE requests.
- Focused tests for identity-auth withdrawal-address calls and all supported server-wallet withdraw payload modes.
- WebSocket subscription/event surface for order events, live sports/esports, market lifecycle, oracle price data, and system messages.

### Changed

- `ServerWalletService.withdraw()` now accepts `on_behalf_of=None` so callers can submit authenticated caller wallet withdrawals to explicit allowed destinations.
- `WithdrawServerWalletInput.on_behalf_of` is now optional and unset optional fields continue to be omitted from the JSON body.
- Server-wallet withdraw docs now describe omitted-destination smart-wallet fallback and explicit whitelisted treasury destinations.
- The server-wallet redeem/withdraw example can optionally allowlist a withdraw destination before submitting the HMAC withdraw request.
- README, examples docs, package metadata, lockfile, and runtime `__version__` now target `v1.0.9`.

## [1.0.8] - 2026-04-30

### Added

- Partner server-wallet allowance recovery endpoints:
  - `PartnerAccountService.check_allowances()`
  - `PartnerAccountService.retry_allowances()`
- Public allowance recovery response models, status constants, and target-level error-code constants.
- New runnable `examples/api_key_v3/partner_account_allowances.py` flow for partner HMAC allowance check and retry operations without admin APIs.

### Changed

- Updated partner allowance recovery models and docs for live-chain retry behavior:
  - target `submitted` status now means the current retry request submitted a sponsored transaction or user operation
  - target-level `IN_FLIGHT_ELSEWHERE`, `RATE_LIMITED`, and `nextRetryAt` modeling was removed
  - success response `retryAfterSeconds` / `nextRetryAt` modeling was removed; `429` retry timing remains available from the raw API error body
  - retry `429` responses raise `RateLimitError`; retry `409` responses raise `ConflictError`
- README, examples docs, package metadata, and runtime `__version__` now target `v1.0.8`.

## [1.0.7]

### Changed

- Migrated portfolio history endpoint from legacy page/limit pagination to cursor-based pagination.
  - `get_user_history()` now accepts `cursor: str | None` instead of `page: int`.
  - First request should omit cursor (or pass `None`); subsequent requests pass the returned `next_cursor`.
  - Default limit changed from 10 to 20 to match API default.
- Updated `HistoryEntry` model to match current API response shape (`block_timestamp`, `strategy`, `transaction_hash`, `market`, etc.).
- Replaced `HistoryResponse.total_count` with `next_cursor: Optional[str]` for cursor-based pagination.
- Added `HistoryMarket` and `HistoryMarketCollateral` models.

## [1.0.6]

### Added

- Server-managed wallet support for delegated-signing partner flows:
  - new `ServerWalletService`
  - new `client.server_wallets` root entrypoint
  - `redeem_positions()` for `POST /portfolio/redeem`
  - `withdraw()` for `POST /portfolio/withdraw`
- New public server-wallet request/response models for redeem and withdraw operations.
- New `ScopeWithdrawal` constant for api-token scope handling.
- New focused tests for server-wallet validation, HMAC-only auth enforcement, and root client composition.
- New partner api-token v3 example covering server-wallet redeem and optional withdraw.

## [1.0.5]

### Added

- `FAK` (Fill-And-Kill) limit-order support alongside existing `GTC` and `FOK` flows.
- `post_only` support for `GTC` orders in the Python client payload surface.
- New public examples and README coverage for:
  - `FAK` limit-order placement
  - `GTC` `post_only` usage

### Changed

- README/examples now document `post_only` as `GTC`-only and omit it for `FAK` / `FOK`.
- Package metadata now targets `v1.0.5`.

## [1.0.4]

### Added

- Partner-facing api-token v3 support:
  - `ApiTokenService` for `get_capabilities()`, `derive_token()`, `list_tokens()`, and `revoke_token()`
  - `PartnerAccountService` for `POST /profiles/partner-accounts`
  - `DelegatedOrderService` for delegated create, cancel by id, and cancel all
- New modular root `Client` that composes shared HTTP transport with:
  - `markets`
  - `market_pages`
  - `portfolio`
  - `api_tokens`
  - `partner_accounts`
  - `delegated_orders`
- HMAC-scoped request signing in `HttpClient` with `HMACCredentials`
- HMAC WebSocket handshake support for authenticated subscriptions
- New partner-facing types:
  - `HMACCredentials`
  - `DeriveApiTokenInput`
  - `DeriveApiTokenResponse`
  - `ApiToken`
  - `PartnerCapabilities`
  - `CreatePartnerAccountInput`
  - `CreatePartnerAccountEOAHeaders`
  - `PartnerAccountResponse`
- New examples under `examples/api_key_v3/`:
  - token lifecycle
  - partner account creation
  - delegated trading
  - narrated e2e flow
  - websocket with HMAC auth
- Focused tests for:
  - HMAC header generation and auth precedence
  - api-token service methods
  - partner-account creation payloads and validation
  - delegated order payloads and cancel helpers
  - root client wiring
  - websocket HMAC propagation

### Changed

- `HttpClient` now supports three auth shapes:
  - standard `X-API-Key`
  - scoped HMAC api-token v3 credentials
  - per-request identity header helpers for Privy-authenticated partner endpoints
- `HttpClient` now maps `400` to `ValidationError` and `409` to new `ConflictError`
- Partner-account client payloads now validate `displayName` length with the backend's `44` character limit
- Standard `X-API-Key` auth remains first-class and unchanged for the existing regular trading flow
- README and examples now document the partner api-token v3 workflow explicitly
- README and examples now clarify that partner HMAC credentials are intended for backend/BFF usage; browser apps should keep public reads in the frontend and route partner-authenticated actions through their own backend

## [1.0.3]

### Added

- New `market_pages` module with `MarketPageFetcher`:
  - `get_navigation()`
  - `get_market_page_by_path()` with manual `301` follow via `Location`
  - `get_markets()` with filters and offset/cursor response handling
  - `get_property_keys()`, `get_property_key()`, `get_property_options()`
- New market-pages type models in `limitless_sdk.types.market_pages`:
  - `NavigationNode`, `MarketPage`, `PropertyKey`, `PropertyOption`
  - `MarketPageMarketsParams`, `MarketPageMarketsOffsetResponse`, `MarketPageMarketsCursorResponse`
- `HttpClient.get_raw()` and `HttpRawResponse` for endpoints requiring access to status/headers (redirect handling).
- New end-to-end example: `examples/09_market_pages_navigation.py`.
- New market-pages test suite: `tests/test_market_page_fetcher.py`.

### Changed

- Updated query serialization to `urlencode(..., doseq=True)` for repeated filter keys (e.g. `ticker=btc&ticker=eth`).
- Hardened `OrderResponse` numeric parsing for `create_order()` payload fields (`makerAmount`, `takerAmount`, `price`, `salt`) with strict number/numeric-string validation and large-integer-safe `salt` parsing.
- Extended market model parity for market-pages payloads:
  - `MarketSettings.rewards_epoch` and `MarketSettings.c` now support string/number values
  - added optional `rebate_rate`
  - added optional market fields (`open_interest`, `liquidity`, `image_url`, `automation_type`, `trends`, `position_ids`, formatted variants)
- Public exports updated to include market-pages fetcher, types, and raw HTTP response type.

## [1.0.2]

### Fixed

- **IEEE 754 float precision in order pricing**: Fixed `OrderBuilder._calculate_amounts()` using `int()` to scale float values to integers, which truncated prices like `0.95` to `949999` instead of `950000`. Changed to `round()` for correct conversion.
- **IEEE 754 float drift in tick-aligned price**: Fixed `OrderBuilder.build_order()` where multiplying back by tick size introduced float noise (e.g., `950 * 0.001` = `0.9500000000000001`). Added `round(price, tick_decimals)` to eliminate drift before sending price to the API.
- **Logger method name mismatch**: Added `warning` alias to `NoOpLogger` and `ConsoleLogger` to match callers using `.warning()` (Python's standard naming) while the interface defined `.warn()`. This caused `AttributeError` crashes when `OrderClient` attempted to log without a custom logger.
- **MakerMatch model missing optional fields**: Made `created_at`, `matched_size`, and `order_id` fields optional in `MakerMatch` to handle API responses that don't include all fields.
- **Validation for 3 decimal places**: API allows only 3 decimals places, and sending can lead API error.

---

## [1.0.0]

### Release Notes

This is the first stable, production-ready release of the Limitless Exchange Python SDK, designated as a **Long-Term Support (LTS)** version. This release consolidates all features and improvements from pre-release versions (v0.x) into a stable, well-documented, and thoroughly tested SDK suitable for production use.

In version 1.0.0 there was done important change to move from Cookie based auth to API-KEY due to /auth endpoint deprication in nearest future.

**LTS Support Policy**: This version will receive security updates, critical bug fixes, API compatibility maintenance, and community support.

### Added

#### Core Features

- **Authentication**
  - API key authentication with X-API-Key header
  - Automatic loading from `LIMITLESS_API_KEY` environment variable
  - EIP-712 message signing for order creation (via `OrderSigner`)
  - `AuthenticationError` for authentication failure handling
- `MarketFetcher` with intelligent venue caching system
- `OrderClient` for comprehensive order management
- `PortfolioFetcher` for position tracking and trading history
- `WebSocketClient` for real-time orderbook updates
- GTC (Good-Till-Cancelled) order support with `price` + `size` parameters
- FOK (Fill-Or-Kill) order support with `maker_amount` parameter
- Order cancellation (single and batch operations)
- Active markets retrieval with pagination and sorting
- Real-time orderbook data access
- CLOB position data retrieval
- Accumulative points tracking

#### Performance & Optimization

- Automatic venue data caching to eliminate redundant API calls
- Connection pooling via aiohttp for efficient HTTP requests
- API key authentication with automatic header injection
- Cache-aware market operations
- Dynamic venue resolution from cache or API

#### Error Handling & Retry

- `@retry_on_errors` decorator with customizable retry logic
- Configurable delays and maximum retry attempts
- Status code-based retry strategies
- Comprehensive `APIError` exception handling with `AuthenticationError`
- Callback hooks for monitoring retry attempts

#### WebSocket Features

- Event-based subscription system with decorators
- Auto-reconnect functionality with configurable delays
- Typed event handlers for orderbook updates
- Connection lifecycle management
- Real-time market price monitoring

#### Logging & Debugging

- `ConsoleLogger` with configurable log levels (DEBUG, INFO, WARN, ERROR)
- Enhanced debug logging for venue operations
- Venue cache monitoring (hits/misses)
- Request/response logging with header visibility
- Performance tracking and observability

#### Token Approval System

- Complete token approval setup guide and example
- CLOB market approval workflows
- NegRisk market dual-approval requirements (exchange + adapter)
- Web3 integration examples
- ERC-20 (USDC) and ERC-1155 (Conditional Tokens) support

#### Configuration & Customization

- Global and per-request custom HTTP headers
- Configurable signing configuration
- Environment-based configuration
- Custom logger support
- Extensible authentication and signing logic

#### Documentation

- Comprehensive README (750+ lines)
- 10 working examples covering all major features:
  - Token approval setup
  - API key authentication with portfolio data
  - GTC BUY/SELL orders
  - FOK BUY/SELL orders
  - Order cancellation
  - Retry handling
  - Auto-retry patterns
  - WebSocket events
- API reference documentation in docstrings
- Architecture overview
- Best practices guide
- Token approval requirements by market type

### Changed

- Improved FOK order documentation with clear BUY vs SELL semantics
- Enhanced GTC order comments for price parameter clarity
- Updated changelog structure to reflect stable release
- Consolidated pre-release versions into historical section

### Fixed

- FOK SELL order documentation now correctly describes `maker_amount` as "shares to sell" instead of "USDC to spend"
- README FOK section now includes both BUY and SELL examples with proper parameter explanations
- GTC order comments clarified: BUY = "maximum price willing to pay", SELL = "minimum price willing to accept"
- Order Type Parameters section now clearly distinguishes BUY vs SELL semantics
- Changelog version numbering corrected from v0.3.0 to proper semantic versioning

### Architecture

- Modular design with clean separation of concerns
- Full Pydantic model integration for type validation and safety
- Type hints throughout codebase
- Async/await support for optimal performance
- Standards compliance with Python async best practices
- Extensible component architecture

### Quality Assurance

- Production-ready code quality
- Comprehensive error handling throughout
- Well-documented public APIs
- Consistent coding patterns and conventions
- Validated against live Base mainnet
- All examples tested and working

---

The following versions were development releases leading to v1.0.0:

## [0.3.1] - 2025-12 (Pre-release)

### Added

- Venue caching system implementation
- Enhanced debug logging for venue operations
- Venue cache hit/miss monitoring
- Warning logs for markets without venue data

### Changed

- Comprehensive venue system documentation
- Best practices guide for venue caching patterns
- Token approval requirements documentation by market type

## [0.3.0] - 2025-11 (Pre-release)

### Added

- Modular architecture refactor
- `HttpClient` with connection pooling via aiohttp
- `OrderClient` for order management with automatic signing
- `MarketFetcher` for market data operations
- `PortfolioFetcher` for portfolio/positions queries
- `WebSocketClient` for real-time orderbook updates
- Event-based subscription system with decorators
- Auto-reconnect functionality with configurable delays
- `MessageSigner` for EIP-712 message signing
- `Authenticator` for EOA authentication flow
- `AuthenticatedClient` wrapper for session management
- `ConsoleLogger` with configurable log levels
- `@retry_on_errors` decorator

### Changed

- Complete architecture overhaul to modular components
- Enhanced authentication system
- Improved order handling with automatic signing
- Updated README to reflect new architecture

## [0.2.0] - 2025-10 (Pre-release)

### Added

- `additional_headers` parameter to `HttpClient`
- Global and per-request header configuration
- `AuthenticatedClient` for auto-retry on session expiration
- WebSocket support for real-time updates
- Retry decorator functionality
- Comprehensive examples directory

### Fixed

- License configuration in pyproject.toml

## [0.1.0] - 2025-09 (Pre-release)

### Added

- Initial release
- EOA authentication with EIP-712 signing
- Market data access
- GTC and FOK order support
- Portfolio tracking
- Basic HTTP client
- Core SDK functionality

---

## Support

For issues, questions, or contributions:

- GitHub Issues: [Create an issue](https://github.com/limitless-labs-group/limitless-exchange-ts-sdk/issues)
- Email: hey@limitless.network

## License

MIT License - see LICENSE file for details.
