"""Tools package for Container-MCP.

This package contains tools for various operations like system commands,
file operations, web access, and knowledge base management.
"""

import logging
from typing import Any

# Import tool creation functions
from .system import create_system_tools
from .file import create_file_tools
from .web import create_web_tools
from .kb import create_kb_tools
from .list import create_list_tools
from .market import create_market_tools
from .rss import create_rss_tools

logger = logging.getLogger(__name__)

def register_all_tools(mcp, config, bash_manager, python_manager, file_manager, web_manager, kb_manager, list_manager, market_manager, rss_manager):
    """Register tools with the MCP instance based on configuration.

    Args:
        mcp: The MCP instance
        config: The application configuration
        bash_manager: The bash manager instance
        python_manager: The python manager instance
        file_manager: The file manager instance
        web_manager: The web manager instance
        kb_manager: The knowledge base manager instance
        list_manager: The list manager instance
        market_manager: The market manager instance
        rss_manager: The RSS manager instance
    """
    logger.info("Registering tools based on configuration...")
    
    # System Tools (Bash, Python)
    if config.tools_enable_system:
        create_system_tools(mcp, bash_manager, python_manager)
        logger.info("System tools (bash, python) ENABLED.")
    else:
        logger.warning("System tools (bash, python) DISABLED by configuration.")
    
    # File Tools
    if config.tools_enable_file:
        create_file_tools(mcp, file_manager)
        logger.info("File tools ENABLED.")
    else:
        logger.warning("File tools DISABLED by configuration.")
    
    # Web Tools
    if config.tools_enable_web:
        create_web_tools(mcp, web_manager)
        logger.info("Web tools (search, scrape, browse) ENABLED.")
    else:
        logger.warning("Web tools (search, scrape, browse) DISABLED by configuration.")
    
    # Knowledge Base Tools
    if config.tools_enable_kb:
        create_kb_tools(mcp, kb_manager)
        logger.info("Knowledge Base tools ENABLED.")
    else:
        logger.warning("Knowledge Base tools DISABLED by configuration.")
    
    # List Tools
    if config.tools_enable_list:
        create_list_tools(mcp, list_manager)
        logger.info("List tools ENABLED.")
    else:
        logger.warning("List tools DISABLED by configuration.")

    # Market Tools
    if config.tools_enable_market:
        create_market_tools(mcp, market_manager)
        logger.info("Market tools ENABLED.")
    else:
        logger.warning("Market tools DISABLED by configuration.")

    # RSS Tools
    if config.tools_enable_rss:
        create_rss_tools(mcp, rss_manager)
        logger.info("RSS tools ENABLED.")
    else:
        logger.warning("RSS tools DISABLED by configuration.")

    logger.info("Tool registration complete.") 