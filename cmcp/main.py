#!/usr/bin/env python3
# cmcp/main.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Main entry point for Container-MCP."""

import os
import sys
import signal
from pathlib import Path
import logging
import asyncio
from typing import Dict, Any, Optional, List

# Load environment file directly
def load_env_file():
    """Load environment variables from .env file."""
    env_file = Path("config/app.env")
    if not env_file.exists():
        raise FileNotFoundError(f"Environment file {env_file} not found")
    
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

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from cmcp.config import load_config
from cmcp.managers import (
    BashManager,
    PythonManager,
    FileManager,
    WebManager,
    KnowledgeBaseManagerV2 as KnowledgeBaseManager,
    ListManager
)
from cmcp.utils.logging import setup_logging
from cmcp.tools import register_all_tools

# Configure logging
logger = logging.getLogger(__name__)

# Custom FastMCP class with health endpoint
class ContainerMCP(FastMCP):
    """Extended FastMCP with health endpoint."""
    
    def sse_app(self, mount_path: str = "") -> Starlette:
        """Create SSE app with health endpoint."""
        # Get the original SSE app
        app = super().sse_app(mount_path)
        
        # Add health endpoint
        async def health_endpoint(request):
            """Simple health check endpoint."""
            return JSONResponse({
                "status": "healthy",
                "service": "Container-MCP",
                "transport": "sse"
            })
        
        # Add the health route to existing routes
        health_route = Route("/health", health_endpoint, methods=["GET"])
        app.router.routes.append(health_route)
        
        return app

# Initialize the MCP server
mcp = ContainerMCP("Container-MCP")

# Load configuration
config = load_config()

# Initialize managers using from_env pattern
bash_manager = BashManager.from_env(config)
python_manager = PythonManager.from_env(config)
file_manager = FileManager.from_env(config)
web_manager = WebManager.from_env(config)
kb_manager = KnowledgeBaseManager.from_env(config)
list_manager = ListManager.from_env(config)

# Set up logging
log_file = os.path.join("logs", "cmcp.log") if os.path.exists("logs") else None
setup_logging(config.log_level, log_file)

# Initialize the knowledge base manager
async def initialize_managers():
    # Only initialize if KB tools are enabled
    if config.tools_enable_kb:
        await kb_manager.initialize()

# Run initialization in event loop
try:
    # Check if we're already running in an event loop
    asyncio.get_running_loop()
    # If we get here, we're in an event loop, so create a task
    asyncio.create_task(initialize_managers())
except RuntimeError:
    # No running event loop, so run the initialization
    asyncio.run(initialize_managers())

# Add a health check tool
@mcp.tool()
async def health_check() -> dict:
    """Get server health status and system information."""
    import datetime
    import platform
    import psutil
    
    # Get system information
    system_info = {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "server": {
            "name": "Container-MCP",
            "host": config.mcp_host,
            "port": config.mcp_port,
            "platform": platform.platform(),
            "python_version": platform.python_version(),
        },
        "system": {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent if hasattr(psutil, 'disk_usage') else None,
        },
        "managers": {
            "bash": "enabled" if config.tools_enable_system else "disabled",
            "python": "enabled" if config.tools_enable_system else "disabled", 
            "file": "enabled" if config.tools_enable_file else "disabled",
            "web": "enabled" if config.tools_enable_web else "disabled",
            "kb": "enabled" if config.tools_enable_kb else "disabled",
        }
    }
    
    return system_info

# Register tools based on configuration flags
register_all_tools(
    mcp,
    config,  # Pass the config object
    bash_manager,
    python_manager,
    file_manager,
    web_manager,
    kb_manager,
    list_manager
)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Parse command line arguments
    test_mode = "--test-mode" in sys.argv
    
    # Make sure environment variables are set (from .env file)
    # For containers, always use port 8000 internally, but bind to specified host
    port = int(os.environ.get("MCP_PORT", config.mcp_port))
    host = os.environ.get("MCP_HOST", config.mcp_host)
    if os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv'):
        port = 8000
        host = os.environ.get("MCP_HOST", "0.0.0.0")
    
    # Allow command-line arguments to override environment settings
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i+1 < len(sys.argv):
            port = int(sys.argv[i+1])
        elif arg == "--host" and i+1 < len(sys.argv):
            host = sys.argv[i+1]
    
    # Directly set host and port in MCP settings
    mcp.settings.host = host
    mcp.settings.port = port
    
    # Set up signal handlers for graceful shutdown
    def handle_shutdown_signal(signum, frame):
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name}, shutting down gracefully...")
        
        # Perform cleanup for managers if needed
        for manager in [bash_manager, python_manager, file_manager, web_manager, kb_manager]:
            if hasattr(manager, 'cleanup'):
                try:
                    logger.info(f"Cleaning up {manager.__class__.__name__}")
                    manager.cleanup()
                except Exception as e:
                    logger.error(f"Error during cleanup of {manager.__class__.__name__}: {e}")
        
        # Stop the MCP server
        if hasattr(mcp, 'shutdown'):
            logger.info("Shutting down MCP server")
            mcp.shutdown()
        
        # Exit
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown_signal)  # Ctrl+C
    signal.signal(signal.SIGTERM, handle_shutdown_signal)  # Termination signal
    
    # Run the server with the appropriate transport
    if test_mode:
        logger.info("Starting Container-MCP in test mode with stdio transport")
        mcp.run(transport="stdio")
    else:
        logger.info(f"Container-MCP server running at {host}:{port}")
        mcp.run(transport="sse") 
