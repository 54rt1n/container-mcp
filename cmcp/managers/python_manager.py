# cmcp/managers/python_manager.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Python Manager for securely executing Python code."""

import asyncio
import os
import tempfile
import shutil
from dataclasses import dataclass
from typing import Any, Optional, Dict

from cmcp.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PythonResult:
    """Result of Python code execution."""
    
    output: str
    error: str
    result: Any = None


class PythonManager:
    """Manager for secure Python code execution."""
    
    def __init__(
        self,
        sandbox_dir: str,
        memory_limit: int = 256,
        timeout_default: int = 30,
        timeout_max: int = 120
    ):
        """Initialize the PythonManager.
        
        Args:
            sandbox_dir: Directory for sandbox operations
            memory_limit: Memory limit in MB
            timeout_default: Default timeout in seconds
            timeout_max: Maximum allowed timeout in seconds
        """
        self.sandbox_dir = sandbox_dir
        self.memory_limit = memory_limit
        self.timeout_default = timeout_default
        self.timeout_max = timeout_max
        
        # Ensure sandbox directory exists
        os.makedirs(self.sandbox_dir, exist_ok=True)
        logger.debug(f"PythonManager initialized with sandbox at {self.sandbox_dir}")
    
    @classmethod
    def from_env(cls, config=None):
        """Create a PythonManager from environment configuration.
        
        Args:
            config: Optional configuration object, loads from environment if not provided
            
        Returns:
            Configured PythonManager instance
        """
        if config is None:
            from cmcp.config import load_config
            config = load_config()
        
        logger.debug("Creating PythonManager from environment configuration")
        return cls(
            sandbox_dir=config.python_config.sandbox_dir,
            memory_limit=config.python_config.memory_limit,
            timeout_default=config.python_config.timeout_default,
            timeout_max=config.python_config.timeout_max
        )
    
    async def execute(self, code: str, timeout: Optional[int] = None) -> PythonResult:
        """Execute Python code in sandbox.
        
        Args:
            code: Python code to execute
            timeout: Optional timeout in seconds, defaults to timeout_default
            
        Returns:
            PythonResult with output, error and result
        """
        # Apply timeout limit
        if timeout is None:
            timeout = self.timeout_default
        timeout = min(timeout, self.timeout_max)
        
        # Create a temporary file for the Python code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', dir=self.sandbox_dir, delete=False) as f:
            f.write(self._generate_wrapper_code(code))
            temp_file = f.name
        
        try:
            # Use environment-aware sandbox command
            sandbox_cmd = self._get_sandbox_command(temp_file)
            logger.debug(f"Executing Python code with wrapper: {temp_file}")
            
            # Execute with asyncio subprocess
            proc = await asyncio.create_subprocess_exec(
                *sandbox_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.sandbox_dir  # Set working directory to sandbox
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
                stdout_text = stdout.decode()
                stderr_text = stderr.decode()
                
                # Parse result from stdout if available
                result = None
                if stdout_text and "RESULT:" in stdout_text:
                    parts = stdout_text.split("RESULT:", 1)
                    output = parts[0]
                    try:
                        import json
                        result = json.loads(parts[1])
                    except Exception as e:
                        logger.warning(f"Failed to parse result: {e}")
                        result = parts[1]
                else:
                    output = stdout_text
                
                logger.debug(f"Python execution completed with exit code: {proc.returncode}")
                return PythonResult(
                    output=output,
                    error=stderr_text,
                    result=result
                )
            except asyncio.TimeoutError:
                proc.kill()
                logger.warning(f"Python execution timed out after {timeout} seconds")
                return PythonResult(
                    output="",
                    error=f"Execution timed out after {timeout} seconds",
                    result=None
                )
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def _generate_wrapper_code(self, code: str) -> str:
        """Generate wrapper code with output capturing and safety measures.
        
        Args:
            code: User's Python code
            
        Returns:
            Wrapped code with safety measures
        """
        return f"""
import sys
import io
import json
import resource
import traceback
import os

# Set working directory to current directory (which will be the sandbox dir)
os.chdir(os.getcwd())

# Redirect stdout to capture output
original_stdout = sys.stdout
original_stderr = sys.stderr
sys.stdout = io.StringIO()
sys.stderr = io.StringIO()

# Set resource limits
resource.setrlimit(resource.RLIMIT_AS, ({self.memory_limit * 1024 * 1024}, {self.memory_limit * 1024 * 1024}))

result = None
try:
    # Execute the user code
    exec_globals = {{'__builtins__': __builtins__}}
    exec_locals = {{}}
    
    exec({repr(code)}, exec_globals, exec_locals)
    
    # Check if the code returned a value
    if '_' in exec_locals:
        result = exec_locals['_']
    
except Exception as e:
    traceback.print_exc()

# Get output
output = sys.stdout.getvalue()
error = sys.stderr.getvalue()

# Restore stdout/stderr
sys.stdout = original_stdout
sys.stderr = original_stderr

# Print the captured output
print(output, end='')
if result is not None:
    try:
        # Try to serialize the result as JSON
        print("RESULT:" + json.dumps(result))
    except:
        # If not serializable, convert to string
        print("RESULT:" + repr(result))

# Print any errors to stderr
if error:
    print(error, file=sys.stderr, end='')
"""
    
    def _get_sandbox_command(self, script_path: str) -> list:
        """Get appropriate sandboxing command based on environment.
        
        Args:
            script_path: Path to the Python script to execute
            
        Returns:
            Command list with appropriate sandboxing wrappers
        """
        python_path = self._get_python_path()
        
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
                python_path, script_path
            ]
        else:
            # Simplified sandbox for local development
            if self._is_firejail_available():
                return [
                    "firejail", "--quiet", 
                    f"--private={self.sandbox_dir}", 
                    python_path, script_path
                ]
            else:
                # Fallback without sandboxing
                logger.warning("Running Python without firejail sandboxing - FOR DEVELOPMENT ONLY")
                return [python_path, script_path]
    
    def _get_python_path(self) -> str:
        """Get the appropriate Python interpreter path.
        
        Returns:
            Path to Python interpreter
        """
        # Check for Python 3.12 in common locations
        python_paths = [
            "/app/.venv/bin/python",
            "/usr/bin/python3.12",
            "/usr/local/bin/python3.12",
            "python3.12",
            "python3",
            "python"
        ]
        
        for path in python_paths:
            if shutil.which(path):
                return path
        
        # Default fallback
        return "python3"
    
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