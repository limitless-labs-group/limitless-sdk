"""Constants and configuration for Limitless Exchange SDK."""

from typing import Dict, Literal


# API Configuration
DEFAULT_API_URL = "https://api.limitless.exchange"
DEFAULT_WS_URL = "wss://ws.limitless.exchange"

# Protocol Constants
PROTOCOL_NAME = "Limitless CTF Exchange"
PROTOCOL_VERSION = "1"

# Network Types
NetworkType = Literal["mainnet", "testnet"]
MarketTypeStr = Literal["CLOB", "NEGRISK"]


# Network Configurations
NETWORK_CONFIG: Dict[NetworkType, Dict[str, any]] = {
    "testnet": {
        "chain_id": 84532,  # Base Sepolia
        "clob_contract": "0xf636e12bb161895453a0c4e312c47319a295913b",
        "negrisk_contract": "0x9d3891970f5E23E911882be926c632a77AA2f7d0",
    },
    "mainnet": {
        "chain_id": 8453,  # Base Mainnet
        "clob_contract": "0xa4409D988CA2218d956BeEFD3874100F444f0DC3",
        "negrisk_contract": "0x5a38afc17F7E97ad8d6C547ddb837E40B4aEDfC6",
    },
}


def get_contract_address(
    market_type: MarketTypeStr = "CLOB", chain_id: int = 8453
) -> str:
    """Get contract address for market type and chain ID.

    Args:
        market_type: Market type ("CLOB" or "NEGRISK")
        chain_id: Chain ID (8453 for mainnet, 84532 for testnet)

    Returns:
        Contract address for the specified market type

    Raises:
        ValueError: If chain ID is not supported

    Example:
        >>> get_contract_address("CLOB", 8453)
        '0xa4409D988CA2218d956BeEFD3874100F444f0DC3'
    """
    # Determine network from chain ID
    network: NetworkType
    if chain_id == 8453:
        network = "mainnet"
    elif chain_id == 84532:
        network = "testnet"
    else:
        raise ValueError(f"Unsupported chain ID: {chain_id}")

    config = NETWORK_CONFIG[network]

    if market_type == "CLOB":
        return config["clob_contract"]
    elif market_type == "NEGRISK":
        return config["negrisk_contract"]
    else:
        raise ValueError(f"Invalid market type: {market_type}")
