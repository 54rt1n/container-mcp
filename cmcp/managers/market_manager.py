# cmcp/managers/market_manager.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Market data manager for stock/crypto queries via yfinance."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf

from cmcp.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MarketResult:
    """Result from a market query."""
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    volume: int
    market_cap: int
    currency: str
    timestamp: str
    success: bool
    error: Optional[str] = None


class MarketManager:
    """Manager for stock/crypto market data via yfinance."""

    def __init__(
        self,
        timeout_default: int = 30,
        timeout_max: int = 60
    ):
        self.timeout_default = timeout_default
        self.timeout_max = timeout_max
        self._executor = ThreadPoolExecutor(max_workers=2)

    @classmethod
    def from_env(cls, config=None) -> "MarketManager":
        """Create MarketManager from environment config."""
        if config is None:
            from cmcp.config import load_config
            config = load_config()

        logger.debug("Creating MarketManager from environment configuration")
        return cls(
            timeout_default=config.market_config.timeout_default,
            timeout_max=config.market_config.timeout_max
        )

    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol to Yahoo Finance format.

        Converts forex pairs like USD/ZAR to USDZAR=X format.
        """
        if "/" in symbol:
            # Forex pair: USD/ZAR -> USDZAR=X
            return symbol.replace("/", "") + "=X"
        return symbol

    async def query(self, symbol: str, period: str = "1d") -> MarketResult:
        """Query stock/crypto price via yfinance."""
        timeout = min(self.timeout_default, self.timeout_max)
        yf_symbol = self._normalize_symbol(symbol)

        def _fetch():
            ticker = yf.Ticker(yf_symbol)
            return ticker.info

        try:
            loop = asyncio.get_running_loop()
            info = await asyncio.wait_for(
                loop.run_in_executor(self._executor, _fetch),
                timeout=timeout
            )

            if not info or info.get("regularMarketPrice") is None:
                return MarketResult(
                    symbol=symbol, name="", price=0.0, change=0.0,
                    change_percent=0.0, volume=0, market_cap=0,
                    currency="", timestamp="", success=False,
                    error=f"Invalid symbol or no data: {symbol}"
                )

            return MarketResult(
                symbol=symbol.upper(),
                name=info.get("shortName", info.get("longName", "")),
                price=float(info.get("regularMarketPrice", 0)),
                change=float(info.get("regularMarketChange", 0)),
                change_percent=float(info.get("regularMarketChangePercent", 0)),
                volume=int(info.get("regularMarketVolume", 0) or 0),
                market_cap=int(info.get("marketCap", 0) or 0),
                currency=info.get("currency", "USD"),
                timestamp=datetime.now(timezone.utc).isoformat(),
                success=True
            )

        except asyncio.TimeoutError:
            logger.warning(f"Market query timed out for {symbol}")
            return MarketResult(
                symbol=symbol, name="", price=0.0, change=0.0,
                change_percent=0.0, volume=0, market_cap=0,
                currency="", timestamp="", success=False,
                error=f"Query timed out after {timeout} seconds"
            )
        except Exception as e:
            logger.error(f"Market query failed for {symbol}: {e}")
            return MarketResult(
                symbol=symbol, name="", price=0.0, change=0.0,
                change_percent=0.0, volume=0, market_cap=0,
                currency="", timestamp="", success=False,
                error=str(e)
            )
