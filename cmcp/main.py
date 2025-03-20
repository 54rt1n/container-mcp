#!/usr/bin/env python3
# cmcp/main.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Main entry point for Container-MCP."""

import os
import sys
from pathlib import Path
import logging

# Load environment file directly
def load_env_file():
    """Load environment variables from .env file."""
    env_file = Path("config/custom.env")
    if not env_file.exists():
        env_file = Path("config/default.env")
    
    if env_file.exists():
        print(f"Loading environment from {env_file}")
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key] = value

# Load environment variables BEFORE importing any other modules
load_env_file()

# Override critical paths if we're not in a container
if not (os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv')):
    # When running locally, use local paths instead of /app
    print("Running in local environment, overriding /app paths")
    current_dir = os.getcwd()
    
    # Overwrite environment paths to use local directories
    os.environ["SANDBOX_ROOT"] = os.path.join(current_dir, "sandbox")
    os.environ["TEMP_DIR"] = os.path.join(current_dir, "temp")
    
    # Create those directories if they don't exist
    os.makedirs(os.environ["SANDBOX_ROOT"], exist_ok=True)
    os.makedirs(os.environ["TEMP_DIR"], exist_ok=True)
    os.makedirs(os.path.join(os.environ["SANDBOX_ROOT"], "bash"), exist_ok=True) 
    os.makedirs(os.path.join(os.environ["SANDBOX_ROOT"], "python"), exist_ok=True)
    os.makedirs(os.path.join(os.environ["SANDBOX_ROOT"], "files"), exist_ok=True)
    os.makedirs(os.path.join(os.environ["SANDBOX_ROOT"], "browser"), exist_ok=True)

import asyncio
from typing import Dict, Any, Optional

from mcp.server.fastmcp import FastMCP

from cmcp.config import load_config
from cmcp.managers.bash_manager import BashManager
from cmcp.managers.python_manager import PythonManager
from cmcp.managers.file_manager import FileManager
from cmcp.managers.web_manager import WebManager
from cmcp.utils.logging import setup_logging

# Configure logging
logger = logging.getLogger(__name__)

# Initialize the MCP server
mcp = FastMCP("Container-MCP")

# Load configuration
config = load_config()

# Initialize managers using from_env pattern
bash_manager = BashManager.from_env(config)
python_manager = PythonManager.from_env(config)
file_manager = FileManager.from_env(config)
web_manager = WebManager.from_env(config)

# Set up logging
log_file = os.path.join("logs", "cmcp.log") if os.path.exists("logs") else None
setup_logging(config.log_level, log_file)

@mcp.tool()
async def system_run_command(command: str, working_dir: Optional[str] = None) -> Dict[str, Any]:
    """Execute a bash command safely in a sandboxed environment.
    
    Args:
        command: The bash command to execute
        working_dir: Optional working directory (ignored in sandbox)
        
    Returns:
        Dictionary containing stdout, stderr, and exit code
    """
    result = await bash_manager.execute(command)
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code
    }

@mcp.tool()
async def system_run_python(code: str, working_dir: Optional[str] = None) -> Dict[str, Any]:
    """Execute Python code in a secure sandbox.
    
    Args:
        code: Python code to execute
        working_dir: Optional working directory (ignored in sandbox)
        
    Returns:
        Dictionary containing output, error, and execution result
    """
    result = await python_manager.execute(code)
    return {
        "output": result.output,
        "error": result.error,
        "result": result.result
    }

@mcp.tool()
async def file_read(path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """Read file contents safely.
    
    Args:
        path: Path to the file (relative to sandbox root)
        encoding: File encoding
        
    Returns:
        Dictionary containing file content and metadata
    """
    try:
        content, metadata = await file_manager.read_file(path)
        return {
            "content": content,
            "size": metadata.size,
            "modified": metadata.modified_time,
            "success": True
        }
    except Exception as e:
        logger.warning(f"Error reading file {path}: {str(e)}")
        return {
            "content": "",
            "error": str(e),
            "success": False
        }

@mcp.tool()
async def file_write(path: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """Write content to a file safely.
    
    Args:
        path: Path to the file (relative to sandbox root)
        content: Content to write
        encoding: File encoding
        
    Returns:
        Dictionary containing success status and file path
    """
    try:
        success = await file_manager.write_file(path, content)
        return {
            "success": success,
            "path": path
        }
    except Exception as e:
        logger.warning(f"Error writing file {path}: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool()
async def file_list(path: str = "/", pattern: Optional[str] = None) -> Dict[str, Any]:
    """List contents of a directory safely.
    
    Args:
        path: Path to the directory (relative to sandbox root)
        pattern: Optional glob pattern to filter files
        
    Returns:
        Dictionary containing directory entries
    """
    try:
        entries = await file_manager.list_directory(path)
        
        # Apply pattern filtering if specified
        if pattern:
            import fnmatch
            entries = [entry for entry in entries if fnmatch.fnmatch(entry["name"], pattern)]
            
        return {
            "entries": entries,
            "path": path,
            "success": True
        }
    except Exception as e:
        logger.warning(f"Error listing directory {path}: {str(e)}")
        return {
            "entries": [],
            "path": path,
            "error": str(e),
            "success": False
        }

@mcp.tool()
async def file_delete(path: str) -> Dict[str, Any]:
    """Delete a file safely.
    
    Args:
        path: Path of the file to delete
        
    Returns:
        Dictionary containing success status and path
    """
    try:
        success = await file_manager.delete_file(path)
        return {
            "success": success,
            "path": path
        }
    except Exception as e:
        logger.warning(f"Error deleting file {path}: {str(e)}")
        return {
            "success": False,
            "path": path,
            "error": str(e)
        }

@mcp.tool()
async def file_move(source: str, destination: str) -> Dict[str, Any]:
    """Move or rename a file safely.
    
    Args:
        source: Source file path
        destination: Destination file path
        
    Returns:
        Dictionary containing success status, source and destination
    """
    try:
        success = await file_manager.move_file(source, destination)
        return {
            "success": success,
            "source": source,
            "destination": destination
        }
    except Exception as e:
        logger.warning(f"Error moving file {source} to {destination}: {str(e)}")
        return {
            "success": False,
            "source": source,
            "destination": destination,
            "error": str(e)
        }

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
    result = await web_manager.scrape_webpage(url, selector)
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
    result = await web_manager.browse_webpage(url)
    return {
        "content": result.content,
        "url": result.url,
        "title": result.title,
        "success": result.success,
        "error": result.error
    }

@mcp.tool()
async def system_env_var(var_name: Optional[str] = None) -> Dict[str, Any]:
    """Get environment variable values.
    
    Args:
        var_name: Specific environment variable to get (optional)
        
    Returns:
        Dictionary containing environment variables
    """
    if var_name:
        return {
            "variables": {var_name: os.environ.get(var_name, "")},
            "requested_var": os.environ.get(var_name, "")
        }
    else:
        # Only return safe environment variables
        safe_env = {}
        for key, value in os.environ.items():
            # Filter out sensitive variables
            if not any(sensitive in key.lower() for sensitive in ["key", "secret", "password", "token", "auth"]):
                safe_env[key] = value
        return {"variables": safe_env}

@mcp.resource("file://{path}")
async def get_file(path: str) -> str:
    """Get file contents as a resource.
    
    Args:
        path: Path to the file (relative to sandbox root)
        
    Returns:
        File contents
    """
    try:
        content, _ = await file_manager.read_file(path)
        return content
    except Exception as e:
        logger.error(f"Error accessing file resource {path}: {str(e)}")
        return f"Error: {str(e)}"

if __name__ == "__main__":
    # Parse command line arguments
    test_mode = "--test-mode" in sys.argv
    
    # Make sure environment variables are set (from .env file)
    # For containers, always use port 8000 internally, but bind to specified host
    if os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv'):
        port = 8000  # Fixed internal port 
        host = os.environ.get("MCP_HOST", "0.0.0.0")  # Default to all interfaces in container
    else:
        # For local development, use the configured port
        port = int(os.environ.get("MCP_PORT", config.mcp_port))
        host = os.environ.get("MCP_HOST", config.mcp_host)
    
    # Directly set host and port in MCP settings
    mcp.settings.host = host
    mcp.settings.port = port
    
    # Run the server with the appropriate transport
    if test_mode:
        logger.info("Starting Container-MCP in test mode with stdio transport")
        mcp.run(transport="stdio")
    else:
        logger.info(f"Container-MCP server running at {host}:{port}")
        mcp.run(transport="sse") 