# cmcp/managers/web_manager.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Web Manager for secure web operations."""

import aiohttp
import asyncio
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

try:
    from playwright.async_api import async_playwright, Error as PlaywrightError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from bs4 import BeautifulSoup

from cmcp.utils.logging import get_logger
from cmcp.config import AppConfig

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
    
    BRAVE_SEARCH_API_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
    
    def __init__(
        self,
        timeout_default: int = 30,
        allowed_domains: Optional[List[str]] = None,
        brave_api_key: Optional[str] = None
    ):
        """Initialize the WebManager.
        
        Args:
            timeout_default: Default timeout in seconds
            allowed_domains: Optional list of allowed domains (None for all)
            brave_api_key: Optional API key for Brave Search API
        """
        self.timeout_default = timeout_default
        self.allowed_domains = allowed_domains
        self.brave_api_key = brave_api_key
        
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright not available. 'web_browse' tool will be limited.")
        
        logger.debug("WebManager initialized")
        if allowed_domains:
            logger.debug(f"Allowed domains: {', '.join(allowed_domains)}")
        else:
            logger.debug("All domains allowed for scraping/browsing.")
            
        if not self.brave_api_key:
            logger.warning("Brave Search API key not configured. 'web_search' tool will not function.")
    
    @classmethod
    def from_env(cls, config: Optional[AppConfig] = None) -> 'WebManager':
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
        # Safely retrieve the key from the loaded config
        brave_key = getattr(config.web_config, 'brave_search_api_key', None)
        
        return cls(
            timeout_default=config.web_config.timeout_default,
            allowed_domains=config.web_config.allowed_domains,
            brave_api_key=brave_key
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
        if self.allowed_domains is None:
            return True
            
        # If allowed_domains is an empty list, block all non-http(s) urls
        if not self.allowed_domains:
            logger.warning(f"No domains explicitly allowed, blocking access to {url}")
            raise ValueError("No domains configured in WEB_ALLOWED_DOMAINS.")
        
        # Parse domain from URL
        domain = urlparse(url).netloc
        
        # Check against allowed domains
        for allowed_domain in self.allowed_domains:
            # Allow exact matches and subdomains
            if domain == allowed_domain or domain.endswith('.' + allowed_domain):
                return True
        
        logger.warning(f"Domain not allowed for scraping/browsing: {domain}")
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
                    
        except ValueError as e:  # Catch domain/URL validation errors
            logger.warning(f"Validation error for browsing {url}: {str(e)}")
            return WebResult(
                content="",
                url=url,
                success=False,
                error=str(e)
            )
        except Exception as e:
            logger.error(f"Unexpected error during browse_webpage for {url}: {str(e)}", exc_info=True)
            return WebResult(
                content="",
                url=url,
                success=False,
                error=f"Unexpected browsing error: {str(e)}"
            )
    
    async def scrape_webpage(self, url: str, selector: Optional[str] = None, timeout: Optional[int] = None) -> WebResult:
        """Scrape basic textual content from a webpage using aiohttp and BeautifulSoup.
        
        Args:
            url: URL to scrape
            selector: Optional CSS selector to extract specific content
            timeout: Optional timeout in seconds
            
        Returns:
            WebResult with page content and metadata
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("BeautifulSoup4 is not installed. Please install it (`pip install beautifulsoup4`) to use scrape_webpage.")
            return WebResult(
                content="",
                url=url,
                success=False,
                error="Dependency missing: BeautifulSoup4 not installed."
            )
        
        request_timeout = timeout if timeout is not None else self.timeout_default
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        try:
            # Validate URL
            self._validate_url(url)
            
            logger.debug(f"Scraping webpage: {url} with selector '{selector}'")
            
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=request_timeout, allow_redirects=True) as response:
                    response.raise_for_status()  # Check for HTTP errors
                    html_content = await response.text()
                    final_url = str(response.url)
            
            soup = BeautifulSoup(html_content, 'html.parser')
            title = soup.title.string.strip() if soup.title else None
            
            if selector:
                elements = soup.select(selector)
                content = "\n".join(el.get_text(strip=True) for el in elements) if elements else ""
                if not content:
                    logger.warning(f"No elements found for selector '{selector}' at {final_url}")
            else:
                # Default text extraction: remove noise, prefer main content
                for element in soup(["script", "style", "header", "footer", "nav", "aside", "form", "noscript", "figure", "img"]):
                    element.extract()
                main = soup.find('main') or soup.find('article') or soup.find('div', role='main') or soup.body
                content = main.get_text(separator="\n", strip=True) if main else ""
                # Further cleanup
                lines = (line.strip() for line in content.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                content = '\n'.join(chunk for chunk in chunks if chunk)
            
            logger.info(f"Successfully scraped text content from: {final_url}")
            return WebResult(
                content=content,
                url=final_url,
                title=title,
                success=True
            )
            
        except (aiohttp.ClientResponseError, aiohttp.ClientError) as e:
            err_msg = f"HTTP error {e.status}: {e.message}" if hasattr(e, 'status') else f"Request error: {str(e)}"
            logger.warning(f"{err_msg} scraping {url}")
            return WebResult(
                content="",
                url=url,
                success=False,
                error=err_msg
            )
        except asyncio.TimeoutError:
            logger.warning(f"Scraping timed out after {request_timeout}s for {url}")
            return WebResult(
                content="",
                url=url,
                success=False,
                error=f"Request timed out after {request_timeout}s."
            )
        except ValueError as e:  # Catch domain/URL validation errors
            logger.warning(f"Validation error for scraping {url}: {str(e)}")
            return WebResult(
                content="",
                url=url,
                success=False,
                error=str(e)
            )
        except Exception as e:
            logger.error(f"Unexpected error scraping {url}: {str(e)}", exc_info=True)
            return WebResult(
                content="",
                url=url,
                success=False,
                error=f"Unexpected scraping error: {str(e)}"
            )
    
    async def search_web(self, query: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """Search the web using the Brave Search API.
        
        Args:
            query: Search query
            timeout: Optional timeout in seconds
            
        Returns:
            Dictionary with search results
        """
        logger.info(f"Performing web search using Brave API for query: '{query}'")
        
        if not self.brave_api_key:
            logger.error("Brave Search API key is missing. Cannot perform web search.")
            return {
                "results": [],
                "query": query,
                "error": "Brave Search API key not configured."
            }
        
        request_timeout = timeout if timeout is not None else self.timeout_default
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.brave_api_key
        }
        params = {"q": query}
        
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(
                    self.BRAVE_SEARCH_API_ENDPOINT,
                    params=params,
                    timeout=request_timeout
                ) as response:
                    # Handle successful response
                    if response.status == 200:
                        data = await response.json()
                        search_results = []
                        web_data = data.get("web", {})
                        brave_results = web_data.get("results", [])
                        
                        for item in brave_results:
                            title = item.get("title")
                            url = item.get("url")
                            # Use 'description' field for the snippet based on Brave API docs
                            snippet = item.get("description")
                            
                            if title and url:  # Require title and URL
                                search_results.append({
                                    "title": title,
                                    "url": url,
                                    "snippet": snippet or ""  # Ensure snippet is at least an empty string
                                })
                        
                        logger.info(f"Brave Search API returned {len(search_results)} results for query '{query}'")
                        return {
                            "results": search_results,
                            "query": query,
                            "error": None
                        }
                    
                    # Handle specific API errors (e.g., rate limits, bad key)
                    elif response.status in [400, 401, 403, 429, 500]:
                        error_details = await response.text()
                        logger.error(f"Brave Search API returned error {response.status} for query '{query}'. Details: {error_details}")
                        return {
                            "results": [],
                            "query": query,
                            "error": f"API Error {response.status}: {error_details[:200]}"
                        }
                    # Handle other unexpected HTTP errors
                    else:
                        error_details = await response.text()
                        logger.error(f"Unexpected HTTP status {response.status} from Brave Search API for query '{query}'. Details: {error_details}")
                        return {
                            "results": [],
                            "query": query,
                            "error": f"Unexpected API HTTP Status {response.status}. Details: {error_details[:200]}"
                        }
                        
        # Handle network/client errors
        except aiohttp.ClientResponseError as e:
            logger.error(f"HTTP client response error during Brave Search API request for '{query}': {e.status} {e.message}", exc_info=True)
            return {
                "results": [],
                "query": query,
                "error": f"HTTP error {e.status}: {e.message}"
            }
        except aiohttp.ClientError as e:
            logger.error(f"Network error during Brave Search API request for '{query}': {e}", exc_info=True)
            return {
                "results": [],
                "query": query,
                "error": f"Network error connecting to search API: {e}"
            }
        # Handle timeouts
        except asyncio.TimeoutError:
            logger.error(f"Brave Search API request timed out after {request_timeout} seconds for query '{query}'.")
            return {
                "results": [],
                "query": query,
                "error": "Search API request timed out."
            }
        # Handle JSON decoding errors
        except aiohttp.ContentTypeError as e:
            logger.error(f"Failed to decode JSON response from Brave Search API for query '{query}': {e}", exc_info=True)
            return {
                "results": [],
                "query": query,
                "error": "Failed to decode search API response."
            }
        # Handle any other unexpected errors
        except Exception as e:
            logger.error(f"Unexpected error during web search for '{query}': {e}", exc_info=True)
            return {
                "results": [],
                "query": query,
                "error": f"An unexpected error occurred during search: {e}"
            } 