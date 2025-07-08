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
        """Search the web for information using a search engine.
        
        This tool uses web search engines to find relevant information on the internet.
        Returns search results with titles, URLs, and content snippets.
        
        Examples:
        
        Request: {"name": "web_search", "parameters": {"query": "Python async programming best practices"}}
        Response: {"results": [{"title": "Async/Await in Python", "url": "...", "snippet": "..."}]}
        
        Request: {"name": "web_search", "parameters": {"query": "latest news on artificial intelligence 2024"}}
        Response: {"results": [{"title": "AI Breakthroughs 2024", "url": "...", "snippet": "..."}]}
        """
        return await web_manager.search_web(query)
    
    @mcp.tool()
    async def web_scrape(url: str, selector: Optional[str] = None) -> Dict[str, Any]:
        """Extract content from a specific webpage.
        
        This tool fetches and extracts content from any accessible webpage. 
        Optionally use CSS selectors to target specific elements on the page.
        Returns the page content, title, and metadata.
        
        Examples:
        
        Request: {"name": "web_scrape", "parameters": {"url": "https://example.com/article"}}
        Response: {"content": "Full page text...", "title": "Article Title", "url": "https://example.com/article", "success": true}
        
        Request: {"name": "web_scrape", "parameters": {"url": "https://news.site.com", "selector": ".article-content"}}
        Response: {"content": "Only article content...", "title": "News Site", "url": "https://news.site.com", "success": true}
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
        """Interactively browse a website using a full browser engine.
        
        This tool opens a webpage in a browser environment (Playwright) for more complex
        interactions or when dealing with JavaScript-heavy sites. Use this when simple
        scraping doesn't work or when you need to interact with dynamic content.
        
        Examples:
        
        Request: {"name": "web_browse", "parameters": {"url": "https://dynamic-app.com"}}
        Response: {"content": "Rendered page content...", "title": "Dynamic App", "url": "https://dynamic-app.com", "success": true}
        
        Request: {"name": "web_browse", "parameters": {"url": "https://spa-application.com/dashboard"}}
        Response: {"content": "Single page app content...", "title": "Dashboard", "url": "https://spa-application.com/dashboard", "success": true}
        """
        result: WebResult = await web_manager.browse_webpage(url)
        return {
            "content": result.content,
            "url": result.url,
            "title": result.title,
            "success": result.success,
            "error": result.error
        } 