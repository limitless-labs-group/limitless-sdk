# Changelog

All notable changes to the Limitless Exchange Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-15

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
- Email: support@limitless.ai

## License

MIT License - see LICENSE file for details.
