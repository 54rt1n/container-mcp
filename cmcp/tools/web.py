"""Web tools module.

This module contains tools for web operations like searching and scraping.
"""

from typing import Dict, Any, Optional
import logging
from mcp.server.fastmcp import FastMCP
from cmcp.managers.web_manager import WebManager, WebResult

logger = logging.getLogger(__name__)

def create_web_tools(mcp: FastMCP, web_manager: WebManager) -> None:
    """Create and register web tools.
    
    Args:
        mcp: The MCP instance
        web_manager: The web manager instance
    """
    @mcp.tool()
    async def web_search(query: str) -> Dict[str, Any]:
        """Use a search engine to find information on the web.
        
        Args:
            query: The query to search the web for
            
        Returns:
            Dictionary containing search results
        """
        return await web_manager.search_web(query)
    
    @mcp.tool()
    async def web_scrape(url: str, selector: Optional[str] = None) -> Dict[str, Any]:
        """Scrape a specific URL and return the content.
        
        Args:
            url: The URL to scrape
            selector: Optional CSS selector to target specific content
            
        Returns:
            Dictionary containing page content and metadata
        """
        result: WebResult = await web_manager.scrape_webpage(url, selector)
        return {
            "content": result.content,
            "url": result.url,
            "title": result.title,
            "success": result.success,
            "error": result.error
        }
    
    @mcp.tool()
    async def web_browse(url: str) -> Dict[str, Any]:
        """Interactively browse a website using Playwright.
        
        Args:
            url: Starting URL for browsing session
            
        Returns:
            Dictionary containing page content and metadata
        """
        result: WebResult = await web_manager.browse_webpage(url)
        return {
            "content": result.content,
            "url": result.url,
            "title": result.title,
            "success": result.success,
            "error": result.error
        } 