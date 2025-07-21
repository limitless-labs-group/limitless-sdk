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


def test_enums():
    """Test that enums are properly defined."""
    assert OrderSide.BUY == 0
    assert OrderSide.SELL == 1
    
    assert OrderType.LIMIT.value == "LIMIT"
    assert OrderType.MARKET.value == "MARKET"


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


def test_additional_headers_initialization():
    """Test that additional_headers are properly stored during initialization."""
    private_key = "0x" + "a" * 64
    additional_headers = {"x-secret-bypass": "secret-token", "x-custom": "value"}
    
    client = LimitlessClient(private_key=private_key, additional_headers=additional_headers)
    
    assert client.additional_headers == additional_headers
    
    # Test with no additional headers
    client_no_headers = LimitlessClient(private_key=private_key)
    assert client_no_headers.additional_headers == {}


@pytest.mark.asyncio
async def test_additional_headers_in_session():
    """Test that additional_headers are included in session headers."""
    private_key = "0x" + "a" * 64
    additional_headers = {"x-secret-bypass": "secret-token", "x-custom": "value"}
    
    client = LimitlessClient(private_key=private_key, additional_headers=additional_headers)
    
    with patch('aiohttp.ClientSession') as mock_session:
        await client.create_session()
        
        # Verify that ClientSession was called with headers including additional_headers
        mock_session.assert_called_once()
        call_kwargs = mock_session.call_args[1]
        
        assert 'headers' in call_kwargs
        headers = call_kwargs['headers']
        
        # Check that default headers are present
        assert headers['Content-Type'] == 'application/json'
        
        # Check that additional headers are present
        assert headers['x-secret-bypass'] == 'secret-token'
        assert headers['x-custom'] == 'value' 