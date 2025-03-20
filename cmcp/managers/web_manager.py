# cmcp/managers/web_manager.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Web Manager for secure web operations."""

import asyncio
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

try:
    from playwright.async_api import async_playwright, Error as PlaywrightError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

import requests
from bs4 import BeautifulSoup

from cmcp.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class WebResult:
    """Result of a web operation."""
    
    content: str
    url: str
    title: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


class WebManager:
    """Manager for secure web operations."""
    
    def __init__(
        self,
        timeout_default: int = 30,
        allowed_domains: Optional[List[str]] = None
    ):
        """Initialize the WebManager.
        
        Args:
            timeout_default: Default timeout in seconds
            allowed_domains: Optional list of allowed domains (None for all)
        """
        self.timeout_default = timeout_default
        self.allowed_domains = allowed_domains
        
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright not available. Some web features will be limited.")
        
        logger.debug("WebManager initialized")
        if allowed_domains:
            logger.debug(f"Allowed domains: {', '.join(allowed_domains)}")
        else:
            logger.debug("All domains allowed")
    
    @classmethod
    def from_env(cls, config=None):
        """Create a WebManager from environment configuration.
        
        Args:
            config: Optional configuration object, loads from environment if not provided
            
        Returns:
            Configured WebManager instance
        """
        if config is None:
            from cmcp.config import load_config
            config = load_config()
        
        logger.debug("Creating WebManager from environment configuration")
        return cls(
            timeout_default=config.web_config.timeout_default,
            allowed_domains=config.web_config.allowed_domains
        )
    
    def _validate_url(self, url: str) -> bool:
        """Validate URL against allowed domains.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is allowed, raises ValueError otherwise
            
        Raises:
            ValueError: If domain is not allowed
        """
        if not url.startswith(('http://', 'https://')):
            logger.warning(f"Invalid URL scheme: {url}")
            raise ValueError(f"URL must start with http:// or https:// (got: {url})")
        
        # If no domain restrictions, allow all
        if not self.allowed_domains:
            return True
        
        # Parse domain from URL
        domain = urlparse(url).netloc
        
        # Check against allowed domains
        for allowed_domain in self.allowed_domains:
            # Allow exact matches and subdomains
            if domain == allowed_domain or domain.endswith('.' + allowed_domain):
                return True
        
        logger.warning(f"Domain not allowed: {domain}")
        raise ValueError(f"Domain not allowed: {domain}. Allowed domains: {', '.join(self.allowed_domains)}")
    
    async def browse_webpage(self, url: str, timeout: Optional[int] = None) -> WebResult:
        """Browse a webpage using Playwright.
        
        Args:
            url: URL to browse
            timeout: Optional timeout in seconds
            
        Returns:
            WebResult with page content and metadata
        """
        if not PLAYWRIGHT_AVAILABLE:
            return WebResult(
                content="",
                url=url,
                success=False,
                error="Playwright not available. Please install with 'pip install playwright' and run 'playwright install'"
            )
        
        # Apply timeout
        if timeout is None:
            timeout = self.timeout_default
        
        try:
            # Validate URL
            self._validate_url(url)
            
            logger.debug(f"Browsing webpage: {url}")
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                )
                
                # Create page and handle timeout
                page = await context.new_page()
                page.set_default_timeout(timeout * 1000)  # Playwright uses ms
                
                try:
                    # Navigate to URL
                    await page.goto(url, wait_until="domcontentloaded")
                    
                    # Get page title
                    title = await page.title()
                    
                    # Extract page content
                    content = await page.content()
                    
                    return WebResult(
                        content=content,
                        url=page.url,
                        title=title,
                        success=True
                    )
                except PlaywrightError as e:
                    logger.warning(f"Error browsing {url}: {str(e)}")
                    return WebResult(
                        content="",
                        url=url,
                        success=False,
                        error=f"Error browsing webpage: {str(e)}"
                    )
                finally:
                    await context.close()
                    await browser.close()
                    
        except Exception as e:
            logger.error(f"Failed to browse {url}: {str(e)}")
            return WebResult(
                content="",
                url=url,
                success=False,
                error=str(e)
            )
    
    async def scrape_webpage(self, url: str, selector: Optional[str] = None, timeout: Optional[int] = None) -> WebResult:
        """Scrape a webpage using requests and BeautifulSoup.
        
        Args:
            url: URL to scrape
            selector: Optional CSS selector to extract specific content
            timeout: Optional timeout in seconds
            
        Returns:
            WebResult with page content and metadata
        """
        # Apply timeout
        if timeout is None:
            timeout = self.timeout_default
        
        try:
            # Validate URL
            self._validate_url(url)
            
            logger.debug(f"Scraping webpage: {url}")
            # Make request
            response = requests.get(
                url, 
                timeout=timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
            )
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title
            title = soup.title.string if soup.title else None
            
            # Extract content based on selector
            if selector:
                selected_elements = soup.select(selector)
                if selected_elements:
                    content = "\n".join(element.get_text(strip=True) for element in selected_elements)
                else:
                    content = f"No elements found matching selector: {selector}"
            else:
                # Extract main text content
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.extract()
                
                # Get text
                content = soup.get_text(separator="\n")
                
                # Clean up whitespace
                content = re.sub(r'\n+', '\n', content)
                content = re.sub(r' +', ' ', content)
                content = content.strip()
            
            return WebResult(
                content=content,
                url=response.url,
                title=title,
                success=True
            )
            
        except requests.RequestException as e:
            logger.warning(f"Request error for {url}: {str(e)}")
            return WebResult(
                content="",
                url=url,
                success=False,
                error=f"Request error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Failed to scrape {url}: {str(e)}")
            return WebResult(
                content="",
                url=url,
                success=False,
                error=str(e)
            )
    
    async def search_web(self, query: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """Search the web using a search engine API.
        
        Args:
            query: Search query
            timeout: Optional timeout in seconds
            
        Returns:
            Dictionary with search results
        """
        # This is a placeholder for actual search implementation
        # In a real implementation, you would use a search API like Bing, Google, or DuckDuckGo
        
        logger.debug(f"Searching web for: {query}")
        
        # Apply timeout
        if timeout is None:
            timeout = self.timeout_default
        
        try:
            # For now, we'll just scrape a search engine
            encoded_query = query.replace(' ', '+')
            search_url = f"https://www.google.com/search?q={encoded_query}"
            
            result = await self.scrape_webpage(search_url, timeout=timeout)
            
            if not result.success:
                return {
                    "results": [],
                    "query": query,
                    "error": result.error
                }
            
            # Parse simple results from content (this is very simplified)
            # In a real implementation, you'd properly parse the search results
            soup = BeautifulSoup(result.content, 'html.parser')
            
            search_results = []
            for result_div in soup.find_all('div', class_='g'):
                # Extract title, URL and snippet
                title_elem = result_div.find('h3')
                link_elem = result_div.find('a')
                snippet_elem = result_div.find('div', class_='VwiC3b')
                
                if title_elem and link_elem and snippet_elem:
                    title = title_elem.get_text()
                    url = link_elem.get('href')
                    if url.startswith('/url?q='):
                        url = url.split('/url?q=')[1].split('&')[0]
                    snippet = snippet_elem.get_text()
                    
                    search_results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet
                    })
            
            return {
                "results": search_results[:5],  # Limit to first 5 results
                "query": query
            }
            
        except Exception as e:
            logger.error(f"Failed to search for {query}: {str(e)}")
            return {
                "results": [],
                "query": query,
                "error": str(e)
            } 