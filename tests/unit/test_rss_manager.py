# tests/unit/test_rss_manager.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Unit tests for RssManager."""

import pytest
from unittest.mock import patch, MagicMock

from cmcp.managers.rss_manager import RssManager, RssResult, RssItem


class TestRssManager:
    """Tests for RssManager."""

    def test_init(self):
        """Test RssManager initialization."""
        manager = RssManager(timeout_default=15, timeout_max=30, user_agent="test/1.0")
        assert manager.timeout_default == 15
        assert manager.timeout_max == 30
        assert manager.user_agent == "test/1.0"

    @pytest.mark.asyncio
    @patch('cmcp.managers.rss_manager.feedparser')
    async def test_fetch_valid_feed(self, mock_feedparser, rss_manager):
        """Test fetching a valid RSS feed."""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.feed = {"title": "Test Feed", "link": "https://example.com/"}
        mock_feed.entries = [
            {"title": "Article 1", "link": "https://example.com/1", "published": "2024-01-15", "summary": "Summary 1"},
            {"title": "Article 2", "link": "https://example.com/2", "published": "2024-01-14", "summary": "Summary 2"}
        ]
        mock_feedparser.parse.return_value = mock_feed

        result = await rss_manager.fetch("https://example.com/rss")

        assert result.success is True
        assert result.feed_title == "Test Feed"
        assert result.item_count == 2
        assert result.items[0].title == "Article 1"

    @pytest.mark.asyncio
    @patch('cmcp.managers.rss_manager.feedparser')
    async def test_fetch_with_limit(self, mock_feedparser, rss_manager):
        """Test fetching with a limit parameter."""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.feed = {"title": "Test Feed", "link": "https://example.com/"}
        mock_feed.entries = [
            {"title": f"Article {i}", "link": f"https://example.com/{i}"}
            for i in range(10)
        ]
        mock_feedparser.parse.return_value = mock_feed

        result = await rss_manager.fetch("https://example.com/rss", limit=3)

        assert result.success is True
        assert result.item_count == 3

    @pytest.mark.asyncio
    @patch('cmcp.managers.rss_manager.feedparser')
    async def test_fetch_malformed_feed(self, mock_feedparser, rss_manager):
        """Test handling a malformed feed."""
        mock_feed = MagicMock()
        mock_feed.bozo = True
        mock_feed.bozo_exception = "XML parsing error"
        mock_feed.entries = []
        mock_feedparser.parse.return_value = mock_feed

        result = await rss_manager.fetch("https://example.com/bad-rss")

        assert result.success is False
        assert "Failed to parse" in result.error

    @pytest.mark.asyncio
    @patch('cmcp.managers.rss_manager.feedparser')
    async def test_fetch_exception(self, mock_feedparser, rss_manager):
        """Test handling exceptions during fetch."""
        mock_feedparser.parse.side_effect = Exception("Connection refused")

        result = await rss_manager.fetch("https://example.com/rss")

        assert result.success is False
        assert "Connection refused" in result.error

    @pytest.mark.asyncio
    @patch('cmcp.managers.rss_manager.feedparser')
    async def test_fetch_with_atom_fields(self, mock_feedparser, rss_manager):
        """Test fetching an Atom feed with updated instead of published."""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.feed = {"title": "Atom Feed", "link": "https://example.com/"}
        mock_feed.entries = [
            {"title": "Entry 1", "link": "https://example.com/1", "updated": "2024-01-15", "description": "Desc 1"}
        ]
        mock_feedparser.parse.return_value = mock_feed

        result = await rss_manager.fetch("https://example.com/atom")

        assert result.success is True
        assert result.items[0].published == "2024-01-15"
        assert result.items[0].summary == "Desc 1"

    @pytest.mark.asyncio
    @patch('cmcp.managers.rss_manager.feedparser')
    async def test_fetch_empty_url(self, mock_feedparser, rss_manager):
        """Test fetching with empty URL."""
        mock_feedparser.parse.side_effect = Exception("Invalid URL")

        result = await rss_manager.fetch("")

        assert result.success is False
        assert "Invalid URL" in result.error

    @pytest.mark.asyncio
    @patch('cmcp.managers.rss_manager.feedparser')
    async def test_fetch_zero_limit(self, mock_feedparser, rss_manager):
        """Test fetching with limit of 0."""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.feed = {"title": "Test Feed", "link": "https://example.com/"}
        mock_feed.entries = [
            {"title": "Article 1", "link": "https://example.com/1"}
        ]
        mock_feedparser.parse.return_value = mock_feed

        result = await rss_manager.fetch("https://example.com/rss", limit=0)

        assert result.success is True
        assert result.item_count == 0

    @pytest.mark.asyncio
    @patch('cmcp.managers.rss_manager.feedparser')
    async def test_fetch_missing_optional_fields(self, mock_feedparser, rss_manager):
        """Test fetching entries with missing optional fields."""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.feed = {"title": "Test Feed", "link": "https://example.com/"}
        mock_feed.entries = [
            {"title": "Article 1", "link": "https://example.com/1"}
            # Missing: published, updated, summary, description
        ]
        mock_feedparser.parse.return_value = mock_feed

        result = await rss_manager.fetch("https://example.com/rss")

        assert result.success is True
        assert result.item_count == 1
        assert result.items[0].title == "Article 1"
        assert result.items[0].published is None
        assert result.items[0].summary is None

    @pytest.mark.asyncio
    async def test_fetch_timeout(self):
        """Test timeout handling."""
        import asyncio
        manager = RssManager(timeout_default=0.001, timeout_max=0.001)

        with patch('cmcp.managers.rss_manager.feedparser') as mock_feedparser:
            # Patch run_in_executor to simulate timeout
            async def mock_executor(*args):
                await asyncio.sleep(10)  # Simulate slow operation
                return MagicMock()

            with patch.object(asyncio, 'get_running_loop') as mock_loop:
                mock_event_loop = MagicMock()
                mock_event_loop.run_in_executor = MagicMock(return_value=mock_executor())
                mock_loop.return_value = mock_event_loop

                result = await manager.fetch("https://example.com/rss")
                # Should timeout
                assert result.success is False
                assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    @patch('cmcp.managers.rss_manager.feedparser')
    async def test_fetch_partial_bozo_with_entries(self, mock_feedparser, rss_manager):
        """Test handling a partially malformed feed that still has entries."""
        mock_feed = MagicMock()
        mock_feed.bozo = True  # Malformed but has entries
        mock_feed.bozo_exception = "Minor XML issue"
        mock_feed.feed = {"title": "Partial Feed", "link": "https://example.com/"}
        mock_feed.entries = [
            {"title": "Article 1", "link": "https://example.com/1"}
        ]
        mock_feedparser.parse.return_value = mock_feed

        result = await rss_manager.fetch("https://example.com/rss")

        # Should succeed since there are entries despite bozo flag
        assert result.success is True
        assert result.item_count == 1
        assert result.items[0].title == "Article 1"
