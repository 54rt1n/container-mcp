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
        timeout_max: int = 120,
        command_restricted: bool = True
    ):
        """Initialize the BashManager.
        
        Args:
            sandbox_dir: Directory for sandbox operations
            allowed_commands: List of allowed bash commands
            timeout_default: Default timeout in seconds
            timeout_max: Maximum allowed timeout in seconds
            command_restricted: Whether to restrict commands to allowed list
        """
        self.sandbox_dir = sandbox_dir
        self.allowed_commands = allowed_commands
        self.timeout_default = timeout_default
        self.timeout_max = timeout_max
        self.command_restricted = command_restricted
        
        # Ensure sandbox directory exists
        os.makedirs(self.sandbox_dir, exist_ok=True)
        logger.debug(f"BashManager initialized with sandbox at {self.sandbox_dir}")
        logger.debug(f"Command restriction {'enabled' if command_restricted else 'disabled'}")
        if command_restricted:
            logger.debug(f"Allowed commands: {', '.join(allowed_commands) if allowed_commands else 'none'}")
    
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
            timeout_max=config.bash_config.timeout_max,
            command_restricted=config.bash_config.command_restricted
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
        
        # Check command against allowed list if restriction is enabled
        base_cmd = os.path.basename(cmd_parts[0])
        if self.command_restricted:
            if not self.allowed_commands:
                logger.warning("No allowed commands configured")
                return BashResult(
                    stdout="", 
                    stderr="Command restrictions enabled but no commands are allowed. Add commands to BASH_ALLOWED_COMMANDS or set COMMAND_RESTRICTED=false",
                    exit_code=1
                )
            
            if base_cmd not in self.allowed_commands:
                logger.warning(f"Command not allowed: {base_cmd}")
                return BashResult(
                    stdout="", 
                    stderr=f"Command not allowed: {base_cmd}. Allowed commands: {', '.join(self.allowed_commands)}",
                    exit_code=1
                )
        else:
            logger.debug(f"Command restrictions disabled, allowing command: {base_cmd}")
        
        # Use direct subprocess with shell=True when restrictions are off for proper wildcard expansion
        if not self.command_restricted:
            logger.debug(f"Using direct subprocess execution with shell=True for command: {command}")
            try:
                # Use synchronous subprocess for simplicity with shell=True
                process = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=self.sandbox_dir
                )
                return BashResult(
                    stdout=process.stdout,
                    stderr=process.stderr,
                    exit_code=process.returncode
                )
            except subprocess.TimeoutExpired:
                logger.warning(f"Command execution timed out after {timeout} seconds")
                return BashResult(
                    stdout="",
                    stderr=f"Command execution timed out after {timeout} seconds",
                    exit_code=124
                )
        
        # For restricted mode, use the sandboxed environment (original implementation)
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