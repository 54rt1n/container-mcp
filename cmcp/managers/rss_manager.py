# cmcp/managers/rss_manager.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""RSS feed manager for fetching and parsing RSS/Atom feeds."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Optional

import feedparser

from cmcp.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RssItem:
    """Single RSS feed item."""
    title: str
    link: str
    published: Optional[str] = None
    summary: Optional[str] = None


@dataclass
class RssResult:
    """Result from an RSS fetch."""
    feed_title: str
    feed_link: str
    items: list[RssItem] = field(default_factory=list)
    item_count: int = 0
    success: bool = True
    error: Optional[str] = None


class RssManager:
    """Manager for RSS/Atom feed operations."""

    def __init__(
        self,
        timeout_default: int = 15,
        timeout_max: int = 30,
        user_agent: str = "container-mcp/1.0"
    ):
        self.timeout_default = timeout_default
        self.timeout_max = timeout_max
        self.user_agent = user_agent
        self._executor = ThreadPoolExecutor(max_workers=2)

    @classmethod
    def from_env(cls, config=None) -> "RssManager":
        """Create RssManager from environment config."""
        if config is None:
            from cmcp.config import load_config
            config = load_config()

        logger.debug("Creating RssManager from environment configuration")
        return cls(
            timeout_default=config.rss_config.timeout_default,
            timeout_max=config.rss_config.timeout_max,
            user_agent=config.rss_config.user_agent
        )

    async def fetch(self, url: str, limit: int = 10) -> RssResult:
        """Fetch and parse an RSS/Atom feed."""
        timeout = min(self.timeout_default, self.timeout_max)

        def _parse():
            return feedparser.parse(url, agent=self.user_agent)

        try:
            loop = asyncio.get_running_loop()
            feed = await asyncio.wait_for(
                loop.run_in_executor(self._executor, _parse),
                timeout=timeout
            )

            if feed.bozo and not feed.entries:
                return RssResult(
                    feed_title="", feed_link=url, items=[], item_count=0,
                    success=False, error=f"Failed to parse feed: {feed.bozo_exception}"
                )

            items = []
            for entry in feed.entries[:limit]:
                published = entry.get('published') or entry.get('updated')
                summary = entry.get('summary') or entry.get('description')
                items.append(RssItem(
                    title=entry.get('title', ''),
                    link=entry.get('link', ''),
                    published=published,
                    summary=summary
                ))

            return RssResult(
                feed_title=feed.feed.get('title', ''),
                feed_link=feed.feed.get('link', url),
                items=items,
                item_count=len(items),
                success=True
            )

        except asyncio.TimeoutError:
            logger.warning(f"RSS fetch timed out for {url}")
            return RssResult(
                feed_title="", feed_link=url, items=[], item_count=0,
                success=False, error=f"Fetch timed out after {timeout} seconds"
            )
        except Exception as e:
            logger.error(f"RSS fetch failed for {url}: {e}")
            return RssResult(
                feed_title="", feed_link=url, items=[], item_count=0,
                success=False, error=str(e)
            )
