"""System tools module.

This module contains tools for system operations like running commands and accessing environment variables.
"""

from typing import Dict, Any, Optional
import os
import logging
from mcp.server.fastmcp import FastMCP
from cmcp.managers.bash_manager import BashManager, BashResult
from cmcp.managers.python_manager import PythonManager, PythonResult

logger = logging.getLogger(__name__)

def create_system_tools(mcp: FastMCP, bash_manager: BashManager, python_manager: PythonManager) -> None:
    """Create and register system tools.
    
    Args:
        mcp: The MCP instance
        bash_manager: The bash manager instance
        python_manager: The python manager instance
    """
    
    @mcp.tool()
    async def system_run_command(command: str, working_dir: Optional[str] = None) -> Dict[str, Any]:
        """Execute a bash command safely in a sandboxed environment.

        See AVAILABLE_COMMANDS.txt for the extensive list of allowed commands.
        
        Args:
            command: The bash command to execute
            working_dir: Optional working directory (ignored in sandbox)
            
        Returns:
            Dictionary containing stdout, stderr, and exit code
        """
        result: BashResult = await bash_manager.execute(command)
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
        result: PythonResult = await python_manager.execute(code)
        return {
            "output": result.output,
            "error": result.error,
            "result": result.result
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
            safe_env: Dict[str, str] = {}
            for key, value in os.environ.items():
                # Filter out sensitive variables
                if not any(sensitive in key.lower() for sensitive in ["key", "secret", "password", "token", "auth"]):
                    safe_env[key] = value
            return {"variables": safe_env, "requested_var": None} 