# cmcp/managers/market_manager.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Market data manager for stock/crypto queries via yfinance."""

import asyncio
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import yfinance as yf

from cmcp.utils.logging import get_logger

logger = get_logger(__name__)

try:
    import pandas as pd
except Exception:  # pragma: no cover - yfinance provides pandas in normal use
    pd = None


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_percent(value: Any) -> Optional[float]:
    number = _to_float(value)
    if number is None:
        return None
    return number * 100


def _format_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if hasattr(value, "to_pydatetime"):
        try:
            return value.to_pydatetime().replace(tzinfo=timezone.utc).isoformat()
        except Exception:
            pass
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    return str(value)


def _format_earnings_date(value: Any) -> Optional[Any]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        formatted = [_format_datetime(item) for item in value]
        return [item for item in formatted if item]
    return _format_datetime(value)


def _format_news_items(news_items: Any, limit: int) -> List[Dict[str, Any]]:
    if not isinstance(news_items, list):
        return []
    items: List[Dict[str, Any]] = []
    for item in news_items[:max(limit, 0)]:
        if not isinstance(item, dict):
            continue
        # yfinance news structure: each item has "id" and "content" at top level
        # The actual news data is nested under "content"
        content = item.get("content", {})
        if not isinstance(content, dict):
            content = {}

        # Extract URL from nested canonicalUrl or clickThroughUrl
        url = ""
        canonical_url = content.get("canonicalUrl", {})
        if isinstance(canonical_url, dict):
            url = canonical_url.get("url", "")
        if not url:
            click_url = content.get("clickThroughUrl", {})
            if isinstance(click_url, dict):
                url = click_url.get("url", "")

        # Extract publisher from nested provider
        publisher = ""
        provider = content.get("provider", {})
        if isinstance(provider, dict):
            publisher = provider.get("displayName", "")

        items.append({
            "title": content.get("title", ""),
            "link": url,
            "publisher": publisher,
            "published": content.get("pubDate", ""),
            "type": content.get("contentType", ""),
        })
    return items


def _compute_rsi(close_series, period: int = 14) -> Optional[float]:
    if close_series is None or len(close_series) < period + 1:
        return None
    delta = close_series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean().iloc[-1]
    avg_loss = loss.rolling(period).mean().iloc[-1]
    if avg_gain is None or avg_loss is None:
        return None
    try:
        avg_gain = float(avg_gain)
        avg_loss = float(avg_loss)
    except (TypeError, ValueError):
        return None
    if math.isnan(avg_gain) or math.isnan(avg_loss):
        return None
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _find_price_at_date(close, target_date) -> Optional[float]:
    """Find the closing price at or just before target_date."""
    if close.empty:
        return None
    # Get dates that are <= target_date
    mask = close.index <= target_date
    if not mask.any():
        return None
    return float(close.loc[mask].iloc[-1])


def _compute_trend(history: Any) -> Optional[Dict[str, Any]]:
    if pd is None or not isinstance(history, pd.DataFrame) or history.empty:
        return None
    if "Close" not in history:
        return None

    close = history["Close"].dropna()
    if close.empty:
        return None

    last_close = float(close.iloc[-1])
    last_index = history.index[-1]
    as_of = _format_datetime(last_index)

    # Convert last_index to a naive datetime for timedelta arithmetic
    if hasattr(last_index, 'to_pydatetime'):
        last_date = last_index.to_pydatetime()
    else:
        last_date = last_index

    # Date-based lookbacks (calendar weeks)
    lookbacks = {
        "1w": timedelta(weeks=1),
        "1m": timedelta(weeks=4),
        "3m": timedelta(weeks=13),
        "6m": timedelta(weeks=26),
        "1y": timedelta(weeks=52),
    }

    prices: Dict[str, Optional[float]] = {}
    returns: Dict[str, Optional[float]] = {}
    for label, delta in lookbacks.items():
        target_date = last_date - delta
        past_price = _find_price_at_date(close, target_date)
        prices[f"price_{label}"] = past_price
        if past_price is not None:
            returns[f"return_{label}"] = (last_close / past_price - 1) * 100
        else:
            returns[f"return_{label}"] = None

    ma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
    ma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
    ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None

    returns_series = close.pct_change().dropna()
    vol_window = returns_series.tail(20) if len(returns_series) >= 20 else returns_series
    volatility_20d = None
    if len(vol_window) >= 2:
        volatility_20d = float(vol_window.std()) * math.sqrt(252) * 100

    rsi14 = _compute_rsi(close, 14)

    history_window = history.tail(252) if len(history) >= 252 else history
    if "High" in history_window and "Low" in history_window:
        range_low = _to_float(history_window["Low"].min())
        range_high = _to_float(history_window["High"].max())
    else:
        range_low = _to_float(history_window["Close"].min())
        range_high = _to_float(history_window["Close"].max())

    last_week_rows = history.tail(5)
    last_week: List[Dict[str, Any]] = []
    if not last_week_rows.empty:
        for idx, row in last_week_rows.iterrows():
            last_week.append({
                "date": _format_datetime(idx),
                "close": _to_float(row.get("Close")),
            })

    return {
        "as_of": as_of,
        "close": last_close,
        **prices,
        **returns,
        "ma20": ma20,
        "ma50": ma50,
        "ma200": ma200,
        "volatility_20d": volatility_20d,
        "rsi14": rsi14,
        "range_52w_low": range_low,
        "range_52w_high": range_high,
        "last_week": last_week,
        "data_points": int(len(close)),
    }


def _extract_fundamentals(info: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "trailing_eps": _to_float(info.get("trailingEps")),
        "forward_eps": _to_float(info.get("forwardEps")),
        "trailing_pe": _to_float(info.get("trailingPE")),
        "forward_pe": _to_float(info.get("forwardPE")),
        "dividend_yield": _to_percent(info.get("dividendYield")),
        "dividend_rate": _to_float(info.get("dividendRate")),
        "payout_ratio": _to_percent(info.get("payoutRatio")),
        "profit_margin": _to_percent(info.get("profitMargins")),
        "operating_margin": _to_percent(info.get("operatingMargins")),
        "gross_margin": _to_percent(info.get("grossMargins")),
        "earnings_date": _format_earnings_date(
            info.get("earningsDate")
            or info.get("earningsTimestampStart")
            or info.get("earningsTimestamp")
        ),
        "earnings_quarterly_growth": _to_percent(info.get("earningsQuarterlyGrowth")),
        "earnings_growth": _to_percent(info.get("earningsGrowth")),
    }


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
    fundamentals: Optional[Dict[str, Any]] = None
    news: Optional[List[Dict[str, Any]]] = None
    trend: Optional[Dict[str, Any]] = None
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

    async def query(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        news_count: int = 5
    ) -> MarketResult:
        """Query stock/crypto price via yfinance."""
        timeout = min(self.timeout_default, self.timeout_max)
        yf_symbol = self._normalize_symbol(symbol)

        def _fetch():
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info
            history = None
            news = None
            try:
                history = ticker.history(period=period, interval=interval)
            except Exception as exc:
                logger.warning(f"Market history fetch failed for {symbol}: {exc}")
            try:
                news = ticker.news
            except Exception as exc:
                logger.warning(f"Market news fetch failed for {symbol}: {exc}")
            return info, history, news

        try:
            loop = asyncio.get_running_loop()
            info, history, news = await asyncio.wait_for(
                loop.run_in_executor(self._executor, _fetch),
                timeout=timeout
            )

            if not info or info.get("regularMarketPrice") is None:
                return MarketResult(
                    symbol=symbol, name="", price=0.0, change=0.0,
                    change_percent=0.0, volume=0, market_cap=0,
                    currency="", timestamp="", success=False,
                    fundamentals=None, news=None, trend=None,
                    error=f"Invalid symbol or no data: {symbol}"
                )

            fundamentals = _extract_fundamentals(info)
            trend = _compute_trend(history)
            news_items = _format_news_items(news, news_count)

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
                success=True,
                fundamentals=fundamentals,
                news=news_items,
                trend=trend
            )

        except asyncio.TimeoutError:
            logger.warning(f"Market query timed out for {symbol}")
            return MarketResult(
                symbol=symbol, name="", price=0.0, change=0.0,
                change_percent=0.0, volume=0, market_cap=0,
                currency="", timestamp="", success=False,
                fundamentals=None, news=None, trend=None,
                error=f"Query timed out after {timeout} seconds"
            )
        except Exception as e:
            logger.error(f"Market query failed for {symbol}: {e}")
            return MarketResult(
                symbol=symbol, name="", price=0.0, change=0.0,
                change_percent=0.0, volume=0, market_cap=0,
                currency="", timestamp="", success=False,
                fundamentals=None, news=None, trend=None,
                error=str(e)
            )
