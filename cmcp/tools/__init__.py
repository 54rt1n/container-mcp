"""Tools package for Container-MCP.

This package contains tools for various operations like system commands,
file operations, web access, and knowledge base management.
"""

from .system import create_system_tools
from .file import create_file_tools
from .web import create_web_tools
from .kb import create_kb_tools

def register_all_tools(mcp, bash_manager, python_manager, file_manager, web_manager):
    """Register all tools with the MCP instance.
    
    Args:
        mcp: The MCP instance
        bash_manager: The bash manager instance
        python_manager: The python manager instance
        file_manager: The file manager instance
        web_manager: The web manager instance
    """
    create_system_tools(mcp, bash_manager, python_manager)
    create_file_tools(mcp, file_manager)
    create_web_tools(mcp, web_manager)
    create_kb_tools(mcp) 