"""
Token Approval Setup Example

This example demonstrates how to set up token approvals before trading on Limitless Exchange.
You need to approve tokens ONCE per wallet before placing orders.

IMPORTANT - Approval Requirements:

Two contracts are involved:
- CTF: ERC-1155 Conditional Tokens contract (hardcoded per chain)
- venue.exchange: Exchange/DEX contract (dynamic per market from API)

CLOB Markets:
- BUY orders: Approve USDC → venue.exchange
- SELL orders: Approve CT → venue.exchange (CTF contract operator approval)

NegRisk Markets:
- BUY orders: Approve USDC → venue.exchange
- SELL orders: Approve CT → venue.exchange AND venue.adapter (TWO operator approvals!)

These approvals are permanent (until revoked) and only need to be set once per wallet.

Setup:
1. Copy .env.example to .env
2. Add your PRIVATE_KEY and MARKET_SLUG
3. Run: python examples/00_setup_approvals.py
"""

import asyncio
import os
from decimal import Decimal
from dotenv import load_dotenv
from eth_account import Account
from web3 import Web3

from limitless_sdk.api import HttpClient
from limitless_sdk.markets import MarketFetcher
from limitless_sdk.utils.constants import get_contract_address, DEFAULT_CHAIN_ID

# Load environment variables
load_dotenv()

# Configuration
API_URL = os.getenv("API_URL", "https://api.limitless.exchange")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
MARKET_SLUG = os.getenv("MARKET_SLUG", "largest-company-end-of-2025-1746118069282")
RPC_URL = os.getenv("RPC_URL", "https://mainnet.base.org")  # Base mainnet
CHAIN_ID = int(os.getenv("CHAIN_ID", str(DEFAULT_CHAIN_ID)))

# ERC-20 approve ABI (for USDC)
ERC20_APPROVE_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]

# ERC-1155 setApprovalForAll ABI (for Conditional Tokens)
ERC1155_APPROVAL_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "operator", "type": "address"},
            {"internalType": "bool", "name": "approved", "type": "bool"},
        ],
        "name": "setApprovalForAll",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "account", "type": "address"},
            {"internalType": "address", "name": "operator", "type": "address"},
        ],
        "name": "isApprovedForAll",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
]


async def setup_approvals():
    """Set up token approvals for trading on Limitless Exchange."""
    print("🔐 Token Approval Setup for Limitless Exchange\n")

    # Validate environment
    if not PRIVATE_KEY:
        print("❌ Error: PRIVATE_KEY not found in .env file")
        print("   Please add your private key to .env")
        return

    # Show configuration
    print("⚙️  Configuration:")
    print(f"   API URL: {API_URL}")
    print(f"   Chain ID: {CHAIN_ID}")
    print(f"   RPC URL: {RPC_URL}")
    print(f"   Market Slug: {MARKET_SLUG}\n")

    # Initialize wallet and Web3
    account = Account.from_key(PRIVATE_KEY)
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    print(f"👛 Wallet Address: {account.address}\n")

    # Check network connectivity
    if not w3.is_connected():
        print("❌ Error: Failed to connect to RPC endpoint")
        print(f"   RPC URL: {RPC_URL}")
        return

    # Verify chain ID
    actual_chain_id = w3.eth.chain_id
    if actual_chain_id != CHAIN_ID:
        print(f"⚠️  Warning: Connected to chain {actual_chain_id}, expected {CHAIN_ID}")
        print("   Please check your RPC_URL and CHAIN_ID in .env")
        return

    print(f"✅ Connected to chain ID: {actual_chain_id}\n")

    # Initialize SDK
    http_client = HttpClient(base_url=API_URL)
    market_fetcher = MarketFetcher(http_client)

    # Fetch market to get venue information
    print(f"📊 Fetching market: {MARKET_SLUG}...")
    try:
        market = await market_fetcher.get_market(MARKET_SLUG)
        print(f"   Market: {market.title}")
        print(f"   Type: {market.market_type}")
    except Exception as e:
        print(f"❌ Error fetching market: {e}")
        return

    # Check if market has venue
    if not market.venue:
        print("❌ Error: Market does not have venue information")
        print("   This market may not support trading via the venue system")
        return

    venue = market.venue
    print(f"   Exchange: {venue.exchange}")
    if venue.adapter:
        print(f"   Adapter: {venue.adapter}")
    else:
        print(f"   Adapter: None (CLOB market - adapter not needed)")
    print()

    # Determine if this is a NegRisk market
    is_negrisk = market.neg_risk_request_id is not None

    # Get contract addresses
    usdc_address = get_contract_address("USDC", CHAIN_ID)
    ctf_address = get_contract_address("CTF", CHAIN_ID)  # ERC-1155 Conditional Tokens contract

    print("📝 Contract Addresses:")
    print(f"   USDC: {usdc_address}")
    print(f"   CTF: {ctf_address}")
    print(f"   Exchange (venue.exchange): {venue.exchange}\n")

    # Create contract instances
    usdc_contract = w3.eth.contract(address=Web3.to_checksum_address(usdc_address), abi=ERC20_APPROVE_ABI)
    ctf_contract = w3.eth.contract(address=Web3.to_checksum_address(ctf_address), abi=ERC1155_APPROVAL_ABI)

    # Check and set up USDC approval for BUY orders
    print("🔍 Checking USDC approval for BUY orders...")
    try:
        current_allowance = usdc_contract.functions.allowance(
            Web3.to_checksum_address(account.address),
            Web3.to_checksum_address(venue.exchange)
        ).call()

        if current_allowance > 0:
            print(f"   ✅ USDC already approved (allowance: {current_allowance})")
        else:
            print("   📝 Approving USDC for venue.exchange...")
            # Approve max uint256
            max_uint256 = 2**256 - 1
            tx = usdc_contract.functions.approve(
                Web3.to_checksum_address(venue.exchange),
                max_uint256
            ).build_transaction({
                'from': account.address,
                'nonce': w3.eth.get_transaction_count(account.address),
                'gas': 100000,
                'maxFeePerGas': w3.eth.gas_price,
                'maxPriorityFeePerGas': w3.eth.max_priority_fee,
                'chainId': CHAIN_ID,
            })

            signed_tx = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print(f"   Transaction sent: {tx_hash.hex()}")

            print("   ⏳ Waiting for confirmation...")
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt['status'] == 1:
                print("   ✅ USDC approval successful!\n")
            else:
                print("   ❌ USDC approval failed\n")
                return

    except Exception as e:
        print(f"   ❌ Error: {e}\n")
        return

    # Check and set up CT approval for SELL orders
    print("🔍 Checking CT approval for SELL orders (venue.exchange)...")
    try:
        is_approved = ctf_contract.functions.isApprovedForAll(
            Web3.to_checksum_address(account.address),
            Web3.to_checksum_address(venue.exchange)
        ).call()

        if is_approved:
            print("   ✅ CT already approved for venue.exchange")
        else:
            print("   📝 Approving CT for venue.exchange...")
            tx = ctf_contract.functions.setApprovalForAll(
                Web3.to_checksum_address(venue.exchange),
                True
            ).build_transaction({
                'from': account.address,
                'nonce': w3.eth.get_transaction_count(account.address),
                'gas': 100000,
                'maxFeePerGas': w3.eth.gas_price,
                'maxPriorityFeePerGas': w3.eth.max_priority_fee,
                'chainId': CHAIN_ID,
            })

            signed_tx = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print(f"   Transaction sent: {tx_hash.hex()}")

            print("   ⏳ Waiting for confirmation...")
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt['status'] == 1:
                print("   ✅ CT approval successful!\n")
            else:
                print("   ❌ CT approval failed\n")
                return

    except Exception as e:
        print(f"   ❌ Error: {e}\n")
        return

    # For NegRisk markets, also approve CT to adapter
    if is_negrisk and venue.adapter:
        print("🔍 NegRisk Market Detected - Checking CT approval for venue.adapter...")
        try:
            is_approved_adapter = ctf_contract.functions.isApprovedForAll(
                Web3.to_checksum_address(account.address),
                Web3.to_checksum_address(venue.adapter)
            ).call()

            if is_approved_adapter:
                print("   ✅ CT already approved for venue.adapter")
            else:
                print("   📝 Approving CT for venue.adapter...")
                tx = ctf_contract.functions.setApprovalForAll(
                    Web3.to_checksum_address(venue.adapter),
                    True
                ).build_transaction({
                    'from': account.address,
                    'nonce': w3.eth.get_transaction_count(account.address),
                    'gas': 100000,
                    'maxFeePerGas': w3.eth.gas_price,
                    'maxPriorityFeePerGas': w3.eth.max_priority_fee,
                    'chainId': CHAIN_ID,
                })

                signed_tx = account.sign_transaction(tx)
                tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                print(f"   Transaction sent: {tx_hash.hex()}")

                print("   ⏳ Waiting for confirmation...")
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

                if receipt['status'] == 1:
                    print("   ✅ CT approval for adapter successful!\n")
                else:
                    print("   ❌ CT approval for adapter failed\n")
                    return

        except Exception as e:
            print(f"   ❌ Error: {e}\n")
            return

    # Summary
    print("=" * 60)
    print("✅ Token Approval Setup Complete!")
    print("=" * 60)
    print()
    print("You can now:")
    print("  - Place BUY orders (USDC approved)")
    print("  - Place SELL orders (CT approved)")
    if is_negrisk:
        print("  - Trade on NegRisk markets (CT approved for both exchange and adapter)")
    print()
    print("These approvals are permanent until you revoke them.")
    print("You only need to run this setup once per wallet.")


if __name__ == "__main__":
    asyncio.run(setup_approvals())
