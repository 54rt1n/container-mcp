# tests/unit/test_market_manager.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Unit tests for MarketManager."""

import pytest
from unittest.mock import patch, MagicMock

from cmcp.managers.market_manager import MarketManager, MarketResult


class TestMarketManager:
    """Tests for MarketManager."""

    def test_init(self):
        """Test MarketManager initialization."""
        manager = MarketManager(timeout_default=30, timeout_max=60)
        assert manager.timeout_default == 30
        assert manager.timeout_max == 60

    @pytest.mark.asyncio
    @patch('cmcp.managers.market_manager.yf')
    async def test_query_valid_symbol(self, mock_yf, market_manager):
        """Test querying a valid stock symbol."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "shortName": "Apple Inc.",
            "regularMarketPrice": 178.52,
            "regularMarketChange": 2.34,
            "regularMarketChangePercent": 1.33,
            "regularMarketVolume": 52341234,
            "marketCap": 2800000000000,
            "currency": "USD"
        }
        mock_yf.Ticker.return_value = mock_ticker

        result = await market_manager.query("AAPL")

        assert result.success is True
        assert result.symbol == "AAPL"
        assert result.name == "Apple Inc."
        assert result.price == 178.52
        assert result.change == 2.34
        assert result.error is None

    @pytest.mark.asyncio
    @patch('cmcp.managers.market_manager.yf')
    async def test_query_invalid_symbol(self, mock_yf, market_manager):
        """Test querying an invalid symbol."""
        mock_ticker = MagicMock()
        mock_ticker.info = {}
        mock_yf.Ticker.return_value = mock_ticker

        result = await market_manager.query("INVALID123")

        assert result.success is False
        assert "Invalid symbol" in result.error

    @pytest.mark.asyncio
    @patch('cmcp.managers.market_manager.yf')
    async def test_query_exception(self, mock_yf, market_manager):
        """Test handling exceptions during query."""
        mock_yf.Ticker.side_effect = Exception("Network error")

        result = await market_manager.query("AAPL")

        assert result.success is False
        assert "Network error" in result.error

    @pytest.mark.asyncio
    async def test_query_timeout(self):
        """Test timeout handling."""
        import asyncio
        manager = MarketManager(timeout_default=0.001, timeout_max=0.001)

        with patch('cmcp.managers.market_manager.yf') as mock_yf:
            # Create a ticker that will block in a way that triggers timeout
            def slow_info_fetch():
                import time
                time.sleep(10)
                return {"regularMarketPrice": 100.0}

            mock_ticker = MagicMock()
            mock_ticker.info = slow_info_fetch()  # This will hang the executor
            mock_yf.Ticker.return_value = mock_ticker

            # Patch run_in_executor to simulate timeout
            async def mock_executor(*args):
                await asyncio.sleep(10)  # Simulate slow operation
                return {}

            with patch.object(asyncio, 'get_running_loop') as mock_loop:
                mock_event_loop = MagicMock()
                mock_event_loop.run_in_executor = MagicMock(return_value=mock_executor())
                mock_loop.return_value = mock_event_loop

                result = await manager.query("AAPL")
                # Should timeout
                assert result.success is False
                assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    @patch('cmcp.managers.market_manager.yf')
    async def test_query_empty_symbol(self, mock_yf, market_manager):
        """Test querying with empty symbol."""
        mock_ticker = MagicMock()
        mock_ticker.info = {}
        mock_yf.Ticker.return_value = mock_ticker

        result = await market_manager.query("")

        assert result.success is False
        assert "Invalid symbol" in result.error

    @pytest.mark.asyncio
    @patch('cmcp.managers.market_manager.yf')
    async def test_query_null_price_data(self, mock_yf, market_manager):
        """Test handling null price in response."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "shortName": "Test Company",
            "regularMarketPrice": None  # Null price
        }
        mock_yf.Ticker.return_value = mock_ticker

        result = await market_manager.query("TEST")

        assert result.success is False
        assert "Invalid symbol or no data" in result.error

    @pytest.mark.asyncio
    @patch('cmcp.managers.market_manager.yf')
    async def test_query_with_optional_fields_missing(self, mock_yf, market_manager):
        """Test query when optional fields are missing."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "regularMarketPrice": 50.0,
            # Missing: shortName, change, volume, marketCap, currency
        }
        mock_yf.Ticker.return_value = mock_ticker

        result = await market_manager.query("TEST")

        assert result.success is True
        assert result.price == 50.0
        assert result.name == ""  # Should default to empty
        assert result.change == 0.0  # Should default to 0
        assert result.volume == 0  # Should default to 0
        assert result.market_cap == 0  # Should default to 0
        assert result.currency == "USD"  # Should default to USD

    def test_normalize_symbol_stock(self, market_manager):
        """Test symbol normalization for regular stock symbols."""
        assert market_manager._normalize_symbol("AAPL") == "AAPL"
        assert market_manager._normalize_symbol("MSFT") == "MSFT"

    def test_normalize_symbol_forex(self, market_manager):
        """Test symbol normalization for forex pairs with slash."""
        assert market_manager._normalize_symbol("USD/ZAR") == "USDZAR=X"
        assert market_manager._normalize_symbol("EUR/USD") == "EURUSD=X"
        assert market_manager._normalize_symbol("GBP/JPY") == "GBPJPY=X"

    @pytest.mark.asyncio
    @patch('cmcp.managers.market_manager.yf')
    async def test_query_forex_pair(self, mock_yf, market_manager):
        """Test querying forex pair converts symbol correctly."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "shortName": "USD/ZAR",
            "regularMarketPrice": 18.52,
            "regularMarketChange": 0.05,
            "regularMarketChangePercent": 0.27,
            "regularMarketVolume": 0,
            "marketCap": 0,
            "currency": "ZAR"
        }
        mock_yf.Ticker.return_value = mock_ticker

        result = await market_manager.query("USD/ZAR")

        # Verify yfinance was called with normalized symbol
        mock_yf.Ticker.assert_called_once_with("USDZAR=X")
        assert result.success is True
        assert result.symbol == "USD/ZAR"  # Original symbol preserved in result
        assert result.price == 18.52
