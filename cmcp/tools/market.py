# cmcp/tools/market.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Market tools for Container-MCP."""

import logging
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

from cmcp.managers.market_manager import MarketManager

logger = logging.getLogger(__name__)


def create_market_tools(mcp: FastMCP, market_manager: MarketManager) -> None:
    """Create and register market tools.

    Args:
        mcp: The MCP instance
        market_manager: The market manager instance
    """

    @mcp.tool()
    async def market_query(symbol: str, period: str = "1d") -> Dict[str, Any]:
        """Query stock or cryptocurrency prices using Yahoo Finance.

        Args:
            symbol: Stock/crypto symbol (e.g., "AAPL", "BTC-USD", "TSLA")
            period: Historical period - "1d", "5d", "1mo", "3mo", "1y" (default: "1d")

        Returns:
            Dict with price data including symbol, name, price, change, volume, etc.

        Examples:

        Request: {"name": "market_query", "parameters": {"symbol": "AAPL"}}
        Response: {"symbol": "AAPL", "name": "Apple Inc.", "price": 178.52, "change": 2.34, "change_percent": 1.33, "volume": 52341234, "market_cap": 2800000000000, "currency": "USD", "timestamp": "2024-01-15T16:00:00Z", "success": true, "error": null}

        Request: {"name": "market_query", "parameters": {"symbol": "BTC-USD"}}
        Response: {"symbol": "BTC-USD", "name": "Bitcoin USD", "price": 43250.00, "change": 1250.00, "change_percent": 2.98, "volume": 28500000000, "market_cap": 847000000000, "currency": "USD", "timestamp": "2024-01-15T16:00:00Z", "success": true, "error": null}
        """
        result = await market_manager.query(symbol, period)
        return {
            "symbol": result.symbol,
            "name": result.name,
            "price": result.price,
            "change": result.change,
            "change_percent": result.change_percent,
            "volume": result.volume,
            "market_cap": result.market_cap,
            "currency": result.currency,
            "timestamp": result.timestamp,
            "success": result.success,
            "error": result.error
        }
