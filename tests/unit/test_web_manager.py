# tests/unit/test_web_manager.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Unit tests for WebManager."""

import os
import pytest
import unittest.mock as mock
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from cmcp.managers.web_manager import WebManager, WebResult


@pytest.mark.asyncio
async def test_url_validation(web_manager):
    """Test URL validation."""
    # Test valid URL with allowed domain
    valid_url = "https://example.com/page"
    assert web_manager._validate_url(valid_url) is True
    
    # Test valid URL with subdomain of allowed domain
    valid_subdomain = "https://subdomain.example.com/page"
    assert web_manager._validate_url(valid_subdomain) is True
    
    # Test invalid URL scheme
    with pytest.raises(ValueError, match="URL must start with http"):
        web_manager._validate_url("ftp://example.com")
    
    # Test URL with disallowed domain
    with pytest.raises(ValueError, match="Domain not allowed"):
        web_manager._validate_url("https://evil.com/hack")


@pytest.mark.asyncio
@patch('cmcp.managers.web_manager.PLAYWRIGHT_AVAILABLE', True)
@patch('cmcp.managers.web_manager.async_playwright')
async def test_browse_webpage(mock_playwright, web_manager):
    """Test webpage browsing."""
    # Mock Playwright setup
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.title = AsyncMock(return_value="Test Page")
    mock_page.content = AsyncMock(return_value="<html><body>Test Content</body></html>")
    mock_page.url = "https://example.com/test"
    
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    
    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    
    mock_playwright_instance = AsyncMock()
    mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
    
    mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance
    
    # Call browse_webpage
    result = await web_manager.browse_webpage("https://example.com/test")
    
    # Verify the result
    assert result.success is True
    assert result.content == "<html><body>Test Content</body></html>"
    assert result.title == "Test Page"
    assert result.url == "https://example.com/test"
    
    # Verify Playwright was called correctly
    mock_playwright_instance.chromium.launch.assert_called_once_with(headless=True)
    mock_page.goto.assert_called_once()
    mock_page.title.assert_called_once()
    mock_page.content.assert_called_once()


@pytest.mark.asyncio
@patch('cmcp.managers.web_manager.requests.get')
async def test_scrape_webpage(mock_get, web_manager):
    """Test webpage scraping."""
    # Mock requests response
    mock_response = MagicMock()
    mock_response.text = """
    <html>
        <head><title>Test Page</title></head>
        <body>
            <div class="content">Test Content</div>
            <div class="sidebar">Sidebar Content</div>
        </body>
    </html>
    """
    mock_response.url = "https://example.com/test"
    mock_response.raise_for_status = MagicMock()
    
    mock_get.return_value = mock_response
    
    # Test general scraping
    result = await web_manager.scrape_webpage("https://example.com/test")
    
    # Verify the result
    assert result.success is True
    assert "Test Content" in result.content
    assert "Sidebar Content" in result.content
    assert result.title == "Test Page"
    assert result.url == "https://example.com/test"
    
    # Test scraping with selector
    result = await web_manager.scrape_webpage("https://example.com/test", selector=".content")
    
    # Verify the selector-based result
    assert result.success is True
    assert result.content == "Test Content"
    assert result.title == "Test Page"
    
    # Test with failing request
    mock_get.side_effect = Exception("Connection error")
    
    result = await web_manager.scrape_webpage("https://example.com/error")
    
    # Verify error handling
    assert result.success is False
    assert "Connection error" in result.error


@pytest.mark.asyncio
@patch('cmcp.managers.web_manager.WebManager.scrape_webpage')
async def test_search_web(mock_scrape, web_manager):
    """Test web search functionality."""
    # Mock the scrape_webpage method
    mock_result = WebResult(
        content="""
        <div class="g">
            <h3>First Result</h3>
            <a href="https://result1.com">Link 1</a>
            <div class="VwiC3b">Description 1</div>
        </div>
        <div class="g">
            <h3>Second Result</h3>
            <a href="https://result2.com">Link 2</a>
            <div class="VwiC3b">Description 2</div>
        </div>
        """,
        url="https://google.com/search?q=test",
        title="Search Results",
        success=True
    )
    mock_scrape.return_value = mock_result
    
    # Call search_web
    results = await web_manager.search_web("test query")
    
    # Verify the search was performed correctly
    mock_scrape.assert_called_once()
    assert "test+query" in mock_scrape.call_args[0][0]
    
    # Test error handling
    mock_scrape.reset_mock()
    mock_scrape.return_value = WebResult(
        content="",
        url="https://google.com/search?q=error",
        success=False,
        error="Search failed"
    )
    
    error_results = await web_manager.search_web("error query")
    assert "error" in error_results
    assert error_results["results"] == []


@pytest.mark.asyncio
async def test_from_env_initialization(test_config):
    """Test .from_env() initialization."""
    # Mock the config loader to return our test config
    import cmcp.config
    original_load_config = cmcp.config.load_config
    cmcp.config.load_config = lambda: test_config

    try:
        # Initialize from environment
        manager = WebManager.from_env()
        
        # Verify the manager was initialized correctly
        assert manager.timeout_default == test_config.web_config.timeout_default
        assert manager.allowed_domains == test_config.web_config.allowed_domains
    finally:
        # Restore the original function
        cmcp.config.load_config = original_load_config 