# cmcp/tools/rss.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""RSS tools for Container-MCP."""

import logging
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

from cmcp.managers.rss_manager import RssManager

logger = logging.getLogger(__name__)


def create_rss_tools(mcp: FastMCP, rss_manager: RssManager) -> None:
    """Create and register RSS tools.

    Args:
        mcp: The MCP instance
        rss_manager: The RSS manager instance
    """

    @mcp.tool()
    async def rss_fetch(url: str, limit: int = 10) -> Dict[str, Any]:
        """Fetch and parse an RSS or Atom feed.

        Args:
            url: RSS feed URL
            limit: Maximum number of items to return (default: 10)

        Returns:
            Dict with feed title, link, items list, and success status.

        Examples:

        Request: {"name": "rss_fetch", "parameters": {"url": "https://news.ycombinator.com/rss"}}
        Response: {"feed_title": "Hacker News", "feed_link": "https://news.ycombinator.com/", "items": [{"title": "Article Title", "link": "https://example.com/article", "published": "2024-01-15T12:00:00Z", "summary": "Article summary..."}], "item_count": 10, "success": true, "error": null}

        Request: {"name": "rss_fetch", "parameters": {"url": "https://feeds.bbci.co.uk/news/rss.xml", "limit": 5}}
        Response: {"feed_title": "BBC News", "feed_link": "https://www.bbc.co.uk/news/", "items": [...], "item_count": 5, "success": true, "error": null}
        """
        result = await rss_manager.fetch(url, limit)
        return {
            "feed_title": result.feed_title,
            "feed_link": result.feed_link,
            "items": [
                {
                    "title": item.title,
                    "link": item.link,
                    "published": item.published,
                    "summary": item.summary
                }
                for item in result.items
            ],
            "item_count": result.item_count,
            "success": result.success,
            "error": result.error
        }
