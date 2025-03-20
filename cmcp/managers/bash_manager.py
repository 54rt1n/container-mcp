# cmcp/managers/bash_manager.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Bash Manager for securely executing bash commands."""

import asyncio
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional

from cmcp.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BashResult:
    """Result of a bash command execution."""
    
    stdout: str
    stderr: str
    exit_code: int


class BashManager:
    """Manager for secure bash command execution."""
    
    def __init__(
        self, 
        sandbox_dir: str,
        allowed_commands: List[str],
        timeout_default: int = 30,
        timeout_max: int = 120
    ):
        """Initialize the BashManager.
        
        Args:
            sandbox_dir: Directory for sandbox operations
            allowed_commands: List of allowed bash commands
            timeout_default: Default timeout in seconds
            timeout_max: Maximum allowed timeout in seconds
        """
        self.sandbox_dir = sandbox_dir
        self.allowed_commands = allowed_commands
        self.timeout_default = timeout_default
        self.timeout_max = timeout_max
        
        # Ensure sandbox directory exists
        os.makedirs(self.sandbox_dir, exist_ok=True)
        logger.debug(f"BashManager initialized with sandbox at {self.sandbox_dir}")
        logger.debug(f"Allowed commands: {', '.join(allowed_commands)}")
    
    @classmethod
    def from_env(cls, config=None):
        """Create a BashManager from environment configuration.
        
        Args:
            config: Optional configuration object, loads from environment if not provided
            
        Returns:
            Configured BashManager instance
        """
        if config is None:
            from cmcp.config import load_config
            config = load_config()
        
        logger.debug("Creating BashManager from environment configuration")
        return cls(
            sandbox_dir=config.bash_config.sandbox_dir,
            allowed_commands=config.bash_config.allowed_commands,
            timeout_default=config.bash_config.timeout_default,
            timeout_max=config.bash_config.timeout_max
        )
    
    async def execute(self, command: str, timeout: Optional[int] = None) -> BashResult:
        """Execute a bash command in sandbox.
        
        Args:
            command: The bash command to execute
            timeout: Optional timeout in seconds, defaults to timeout_default
            
        Returns:
            BashResult with stdout, stderr, and exit code
        """
        # Apply timeout limit
        if timeout is None:
            timeout = self.timeout_default
        timeout = min(timeout, self.timeout_max)
        
        # Parse the command to check against allowed commands
        cmd_parts = command.split()
        if not cmd_parts:
            logger.warning("Empty command received")
            return BashResult(stdout="", stderr="Empty command", exit_code=1)
        
        base_cmd = os.path.basename(cmd_parts[0])
        if base_cmd not in self.allowed_commands:
            logger.warning(f"Command not allowed: {base_cmd}")
            return BashResult(
                stdout="", 
                stderr=f"Command not allowed: {base_cmd}. Allowed commands: {', '.join(self.allowed_commands)}",
                exit_code=1
            )
        
        # Use environment-aware sandbox command
        sandbox_cmd = self._get_sandbox_command(command)
        logger.debug(f"Executing command: {command}")
        logger.debug(f"Sandbox command: {' '.join(sandbox_cmd)}")
        
        # Execute with asyncio subprocess
        proc = await asyncio.create_subprocess_exec(
            *sandbox_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            result = BashResult(
                stdout=stdout.decode(),
                stderr=stderr.decode(),
                exit_code=proc.returncode
            )
            logger.debug(f"Command completed with exit code: {result.exit_code}")
            return result
        except asyncio.TimeoutError:
            proc.kill()
            logger.warning(f"Command execution timed out after {timeout} seconds")
            return BashResult(
                stdout="",
                stderr=f"Command execution timed out after {timeout} seconds",
                exit_code=124
            )
    
    def _get_sandbox_command(self, command: str) -> List[str]:
        """Get appropriate sandboxing command based on environment.
        
        Args:
            command: The user command to execute
            
        Returns:
            Command list with appropriate sandboxing wrappers
        """
        if self._is_container():
            # Full firejail with all security options in container
            return [
                "firejail",
                "--noprofile",
                "--quiet",
                f"--private={self.sandbox_dir}",
                "--private-dev",
                "--private-tmp",
                "--caps.drop=all",
                "--nonewprivs",
                "--noroot",
                "--seccomp",
                "bash", "-c", command
            ]
        else:
            # Simplified sandbox for local development
            if self._is_firejail_available():
                return [
                    "firejail", "--quiet", 
                    f"--private={self.sandbox_dir}", 
                    "bash", "-c", command
                ]
            else:
                # Fallback without sandboxing
                logger.warning("Running without firejail sandboxing - FOR DEVELOPMENT ONLY")
                return ["bash", "-c", command]
    
    def _is_container(self) -> bool:
        """Check if we're running in a container.
        
        Returns:
            True if running in a container environment
        """
        return os.path.exists('/run/.containerenv') or os.path.exists('/.dockerenv')
    
    def _is_firejail_available(self) -> bool:
        """Check if firejail is available.
        
        Returns:
            True if firejail is installed and available
        """
        return shutil.which("firejail") is not None 