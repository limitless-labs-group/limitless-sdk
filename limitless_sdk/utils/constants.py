"""Constants and configuration for Limitless Exchange SDK."""

from typing import Dict, Literal


# API Configuration
DEFAULT_API_URL = "https://api.limitless.exchange"
DEFAULT_WS_URL = "wss://ws.limitless.exchange"

# Protocol Constants
PROTOCOL_NAME = "Limitless CTF Exchange"
PROTOCOL_VERSION = "1"

# Zero address constant
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

# Network Types
NetworkType = Literal["mainnet", "testnet"]
ContractType = Literal["USDC", "CTF"]

# Contract Addresses
# IMPORTANT: Token approval flow uses TWO different contracts:
# 1. USDC approval: USDC.approve(venue.exchange, amount)
# 2. CT operator approval: CTF.setApprovalForAll(venue.exchange, true)
#
# - CTF (below): ERC-1155 Conditional Tokens contract where outcome tokens live
# - venue.exchange (from API): Exchange/DEX contract that needs operator approval
CONTRACT_ADDRESSES: Dict[int, Dict[str, str]] = {
    8453: {  # Base Mainnet
        "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # Native USDC on Base
        "CTF": "0xC9c98965297Bc527861c898329Ee280632B76e18",   # Conditional Token Framework (ERC-1155)
    },
    84532: {  # Base Sepolia (Testnet)
        "USDC": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",  # USDC on Base Sepolia
        "CTF": "0x7D8610E9567d2a6C9FBf66a5A13E9Ba0cb120Bc6",   # Conditional Token Framework (ERC-1155)
    },
}

# Default chain ID
DEFAULT_CHAIN_ID = 8453  # Base Mainnet


def get_contract_address(
    contract_type: ContractType,
    chain_id: int = DEFAULT_CHAIN_ID
) -> str:
    """Get contract address for static contracts (USDC, CTF).

    Token approval flow requires TWO different contracts:
    1. USDC.approve(venue.exchange, amount) - Allow exchange to spend USDC
    2. CTF.setApprovalForAll(venue.exchange, true) - Allow exchange to transfer outcome tokens

    This function provides:
    - USDC: Collateral token (ERC-20) for all markets
    - CTF: Conditional Token Framework (ERC-1155) where outcome tokens live

    The venue.exchange address (CLOB/NEGRISK per market) is obtained from:
    - market.venue.exchange - Exchange contract that needs operator approval

    For NegRisk markets, also approve CT to venue.adapter:
    - CTF.setApprovalForAll(venue.adapter, true)

    Args:
        contract_type: Contract type ("USDC" or "CTF")
        chain_id: Chain ID (8453 for mainnet, 84532 for testnet)

    Returns:
        Contract address for the specified type

    Raises:
        ValueError: If chain ID or contract type is not supported

    Example:
        >>> get_contract_address("USDC", 8453)
        '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'
        >>> get_contract_address("CTF", 8453)
        '0x4D97DCd97eC945f40cF65F87097ACe5EA0476045'
    """
    if chain_id not in CONTRACT_ADDRESSES:
        raise ValueError(f"Unsupported chain ID: {chain_id}")

    if contract_type not in CONTRACT_ADDRESSES[chain_id]:
        raise ValueError(f"Invalid contract type: {contract_type}")

    return CONTRACT_ADDRESSES[chain_id][contract_type]
