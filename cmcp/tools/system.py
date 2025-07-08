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
        """Execute bash commands safely in a sandboxed environment.

        This tool runs shell commands within a secure sandbox with access to common 
        utilities like ls, cat, grep, find, and more. Perfect for system administration
        tasks, file manipulation, or running development tools.

        You can fs_read AVAILABLE_COMMANDS.txt to get a list of available commands.
        
        Examples:
        
        Request: {"name": "system_run_command", "parameters": {"command": "ls -la /tmp"}}
        Response: {"stdout": "total 8\\ndrwxrwxrwt 2 root root 4096 Jan 1 10:00 .\\n...", "stderr": "", "exit_code": 0}
        
        Request: {"name": "system_run_command", "parameters": {"command": "find . -name '*.py' | head -5"}}
        Response: {"stdout": "./main.py\\n./utils.py\\n./config.py", "stderr": "", "exit_code": 0}
        """
        result: BashResult = await bash_manager.execute(command)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code
        }
    
    @mcp.tool()
    async def system_run_python(code: str, working_dir: Optional[str] = None) -> Dict[str, Any]:
        """Execute Python code safely in a sandboxed environment.
        
        This tool runs Python scripts within a secure sandbox with access to standard
        libraries and common packages. Perfect for data analysis, calculations, 
        text processing, or testing code snippets.
        
        Examples:
        
        Request: {"name": "system_run_python", "parameters": {"code": "import math\\nprint(f'Pi is approximately {math.pi:.4f}')"}}
        Response: {"output": "Pi is approximately 3.1416\\n", "error": "", "result": null}
        
        Request: {"name": "system_run_python", "parameters": {"code": "data = [1, 2, 3, 4, 5]\\nresult = sum(data) / len(data)\\nprint(f'Average: {result}')"}}
        Response: {"output": "Average: 3.0\\n", "error": "", "result": null}
        """
        result: PythonResult = await python_manager.execute(code)
        return {
            "output": result.output,
            "error": result.error,
            "result": result.result
        }
    
    @mcp.tool()
    async def system_env_var(var_name: Optional[str] = None) -> Dict[str, Any]:
        """Access environment variables from the sandbox system.
        
        This tool retrieves environment variable values, either a specific variable
        or all safe environment variables. Sensitive variables (containing 'key', 
        'secret', 'password', etc.) are automatically filtered out for security.
        
        Examples:
        
        Request: {"name": "system_env_var", "parameters": {"var_name": "PATH"}}
        Response: {"variables": {"PATH": "/usr/local/bin:/usr/bin:/bin"}, "requested_var": "/usr/local/bin:/usr/bin"}
        
        Request: {"name": "system_env_var", "parameters": {}}
        Response: {"variables": {"HOME": "/home/user", "SHELL": "/bin/bash", "USER": "sandbox"}, "requested_var": null}
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