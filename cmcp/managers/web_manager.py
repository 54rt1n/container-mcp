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
    
    async def _decode_response(self, response: aiohttp.ClientResponse) -> str:
        """Decode response content with fallback encoding handling.

        Args:
            response: aiohttp ClientResponse object

        Returns:
            Decoded HTML content as string
        """
        # First try using the encoding from Content-Type header (aiohttp default)
        try:
            return await response.text()
        except UnicodeDecodeError:
            pass

        # Read raw bytes for fallback decoding
        raw_bytes = await response.read()

        # Try common encodings in order of preference
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        for encoding in encodings:
            try:
                return raw_bytes.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue

        # Last resort: decode with replacement characters
        logger.warning(f"Could not decode response from {response.url}, using replacement characters")
        return raw_bytes.decode('utf-8', errors='replace')

    async def _fetch_html(self, url: str, timeout: Optional[int] = None, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Any]:
        """Fetch HTML content from a URL.

        Args:
            url: URL to fetch
            timeout: Optional timeout in seconds
            session: Optional existing session to use

        Returns:
            Dictionary with response data or error
        """
        request_timeout = timeout if timeout is not None else self.timeout_default
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        try:
            # Validate URL
            self._validate_url(url)

            logger.debug(f"Fetching HTML from: {url}")

            # Use provided session or create a new one
            if session:
                # Use provided session (could be a mock in tests)
                try:
                    async with session.get(url, timeout=request_timeout, allow_redirects=True, headers=headers) as response:
                        response.raise_for_status()
                        html_content = await self._decode_response(response)
                        final_url = str(response.url)
                        return {
                            "html": html_content,
                            "url": final_url,
                            "success": True
                        }
                except Exception as e:
                    logger.error(f"Unexpected error fetching {url}: {str(e)}", exc_info=True)
                    return {
                        "success": False,
                        "url": url,
                        "error": f"Unexpected error: {str(e)}"
                    }
            else:
                # Create our own session
                async with aiohttp.ClientSession(headers=headers) as new_session:
                    async with new_session.get(url, timeout=request_timeout, allow_redirects=True) as response:
                        response.raise_for_status()
                        html_content = await self._decode_response(response)
                        final_url = str(response.url)
                        return {
                            "html": html_content,
                            "url": final_url,
                            "success": True
                        }
        except (aiohttp.ClientResponseError, aiohttp.ClientError) as e:
            err_msg = f"HTTP error {e.status}: {e.message}" if hasattr(e, 'status') else f"Request error: {str(e)}"
            logger.warning(f"{err_msg} fetching {url}")
            return {
                "success": False,
                "url": url,
                "error": err_msg
            }
        except asyncio.TimeoutError:
            logger.warning(f"Request timed out after {request_timeout}s for {url}")
            return {
                "success": False,
                "url": url,
                "error": f"Request timed out after {request_timeout}s."
            }
        except ValueError as e:  # Catch domain/URL validation errors
            logger.warning(f"Validation error for {url}: {str(e)}")
            return {
                "success": False,
                "url": url,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "url": url,
                "error": f"Unexpected error: {str(e)}"
            }

    async def _fetch_brave_search(self, query: str, timeout: Optional[int] = None, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Any]:
        """Fetch search results from Brave Search API.
        
        Args:
            query: Search query
            timeout: Optional timeout in seconds
            session: Optional existing session to use
            
        Returns:
            Dictionary with API response or error
        """
        if not self.brave_api_key:
            return {
                "success": False,
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
            # Use provided session or create a new one
            if session:
                # Use provided session (could be a mock in tests)
                try:
                    async with session.get(
                        self.BRAVE_SEARCH_API_ENDPOINT,
                        params=params,
                        timeout=request_timeout,
                        headers=headers
                    ) as response:
                        status = response.status
                        if status == 200:
                            data = await response.json()
                            return {
                                "data": data,
                                "status": status,
                                "success": True
                            }
                        else:
                            error_text = await response.text()
                            return {
                                "status": status,
                                "error": error_text,
                                "success": False
                            }
                except Exception as e:
                    logger.error(f"Unexpected error during web search for '{query}': {e}", exc_info=True)
                    return {
                        "success": False,
                        "error": f"An unexpected error occurred during search: {e}"
                    }
            else:
                # Create our own session
                async with aiohttp.ClientSession(headers=headers) as new_session:
                    async with new_session.get(
                        self.BRAVE_SEARCH_API_ENDPOINT,
                        params=params,
                        timeout=request_timeout
                    ) as response:
                        status = response.status
                        if status == 200:
                            data = await response.json()
                            return {
                                "data": data,
                                "status": status,
                                "success": True
                            }
                        else:
                            error_text = await response.text()
                            return {
                                "status": status,
                                "error": error_text,
                                "success": False
                            }
        except (aiohttp.ClientResponseError, aiohttp.ClientError) as e:
            err_msg = f"HTTP error {e.status}: {e.message}" if hasattr(e, 'status') else f"Request error: {str(e)}"
            logger.error(f"{err_msg} during Brave Search API request for '{query}'")
            return {
                "success": False,
                "error": err_msg
            }
        except asyncio.TimeoutError:
            logger.error(f"Brave Search API request timed out after {request_timeout} seconds for query '{query}'.")
            return {
                "success": False,
                "error": "Search API request timed out."
            }
        except Exception as e:
            logger.error(f"Unexpected error during web search for '{query}': {e}", exc_info=True)
            return {
                "success": False,
                "error": f"An unexpected error occurred during search: {e}"
            }

    async def scrape_webpage(self, url: str, selector: Optional[str] = None, timeout: Optional[int] = None, session: Optional[aiohttp.ClientSession] = None) -> WebResult:
        """Scrape basic textual content from a webpage using aiohttp and BeautifulSoup.
        
        Args:
            url: URL to scrape
            selector: Optional CSS selector to extract specific content
            timeout: Optional timeout in seconds
            session: Optional existing aiohttp ClientSession to use
            
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
        
        # Fetch HTML content
        response = await self._fetch_html(url, timeout, session)
        
        # Handle fetch errors
        if not response.get("success", False):
            return WebResult(
                content="",
                url=url,
                success=False,
                error=response.get("error", "Unknown error fetching page")
            )
        
        try:
            # Process HTML with BeautifulSoup
            html_content = response["html"]
            final_url = response["url"]
            
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
        except Exception as e:
            logger.error(f"Error processing HTML from {url}: {str(e)}", exc_info=True)
            return WebResult(
                content="",
                url=url,
                success=False,
                error=f"Error processing HTML: {str(e)}"
            )

    async def search_web(self, query: str, timeout: Optional[int] = None, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Any]:
        """Search the web using the Brave Search API.
        
        Args:
            query: Search query
            timeout: Optional timeout in seconds
            session: Optional existing aiohttp ClientSession to use
            
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
        
        # Fetch search results
        response = await self._fetch_brave_search(query, timeout, session)
        
        # Handle fetch errors
        if not response.get("success", False):
            return {
                "results": [],
                "query": query,
                "error": response.get("error", "Unknown search API error")
            }
        
        try:
            # Process the API response
            data = response["data"]
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
        except Exception as e:
            logger.error(f"Error processing search results for '{query}': {str(e)}", exc_info=True)
            return {
                "results": [],
                "query": query,
                "error": f"Error processing search results: {str(e)}"
            } 