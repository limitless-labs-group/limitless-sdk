"""Tests for Limitless SDK client."""

import pytest
from unittest.mock import AsyncMock, patch
from limitless_sdk import LimitlessClient, LimitlessAPIError, RateLimitError
from limitless_sdk.models import OrderSide, OrderType


def test_client_initialization():
    """Test that client initializes correctly."""
    private_key = "0x" + "a" * 64  # Mock private key
    client = LimitlessClient(private_key=private_key)
    
    assert client.base_url == "https://api.limitless.exchange"
    assert client.private_key == private_key
    assert client.account is not None
    assert client.session is None
    assert client.auth_token is None





def test_enums():
    """Test that enums are properly defined."""
    assert OrderSide.BUY == 0
    assert OrderSide.SELL == 1
    
    assert OrderType.LIMIT == "LIMIT"
    assert OrderType.MARKET == "MARKET"


def test_exceptions():
    """Test that custom exceptions work correctly."""
    # Test LimitlessAPIError
    error = LimitlessAPIError("Test error", 400)
    assert str(error) == "Test error"
    assert error.status_code == 400
    
    # Test RateLimitError
    rate_error = RateLimitError("Rate limited")
    assert str(rate_error) == "Rate limited"
    assert rate_error.status_code == 429


@pytest.mark.asyncio
async def test_context_manager():
    """Test that client works as context manager."""
    private_key = "0x" + "a" * 64
    
    with patch.object(LimitlessClient, 'create_session', new_callable=AsyncMock) as mock_create:
        with patch.object(LimitlessClient, 'close_session', new_callable=AsyncMock) as mock_close:
            async with LimitlessClient(private_key=private_key) as client:
                assert isinstance(client, LimitlessClient)
            
            mock_create.assert_called_once()
            mock_close.assert_called_once()


def test_sign_message():
    """Test message signing functionality."""
    private_key = "0x" + "a" * 64
    client = LimitlessClient(private_key=private_key)
    
    message = "Test message"
    signature = client.sign_message(message)
    
    assert isinstance(signature, str)
    assert len(signature) == 130  # 65 bytes * 2 chars per byte (no 0x prefix)
    # Verify it's a valid hex string
    int(signature, 16) 