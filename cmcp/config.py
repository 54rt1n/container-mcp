# cmcp/config.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Configuration module for Container-MCP."""

import os
import logging
import tempfile
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator

# Configure logging
logger = logging.getLogger(__name__)


# Detect environment
def is_in_container() -> bool:
    """Check if we're running inside a container."""
    return os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv')


# Determine base paths
def get_base_paths() -> Dict[str, str]:
    """Get base paths based on environment."""
    if is_in_container():
        logger.info("Running in container environment")
        return {
            "base_dir": "/app",
            "sandbox_root": "/app/sandbox",
            "temp_dir": "/app/temp"
        }
    else:
        logger.info("Running in local environment")
        # When running locally, use current directory or temp directory
        cwd = os.getcwd()
        
        # Check if we can use local directories
        sandbox_dir = os.path.join(cwd, "sandbox")
        temp_dir = os.path.join(cwd, "temp")
        
        # If we can't create/access these directories, fall back to temp
        try:
            os.makedirs(sandbox_dir, exist_ok=True)
            os.makedirs(temp_dir, exist_ok=True)
        except (PermissionError, OSError):
            logger.warning("Cannot use local directories, falling back to temp directory")
            base_temp = tempfile.gettempdir()
            sandbox_dir = os.path.join(base_temp, "cmcp-sandbox")
            temp_dir = os.path.join(base_temp, "cmcp-temp")
            os.makedirs(sandbox_dir, exist_ok=True)
            os.makedirs(temp_dir, exist_ok=True)
        
        return {
            "base_dir": cwd,
            "sandbox_root": sandbox_dir,
            "temp_dir": temp_dir
        }


# Get paths for current environment
BASE_PATHS = get_base_paths()


class BashConfig(BaseModel):
    """Configuration for Bash Manager."""

    sandbox_dir: str = Field(default=BASE_PATHS["sandbox_root"])
    allowed_commands: List[str] = Field(default_factory=list)
    command_restricted: bool = Field(default=True)
    timeout_default: int = Field(default=30)
    timeout_max: int = Field(default=120)


class PythonConfig(BaseModel):
    """Configuration for Python Manager."""

    sandbox_dir: str = Field(default=BASE_PATHS["sandbox_root"])
    memory_limit: int = Field(default=256)
    timeout_default: int = Field(default=30)
    timeout_max: int = Field(default=120)


class FileSystemConfig(BaseModel):
    """Configuration for File Manager."""

    base_dir: str = Field(default=BASE_PATHS["sandbox_root"])
    max_file_size_mb: int = Field(default=10)
    allowed_extensions: List[str] = Field(default_factory=list)


class WebConfig(BaseModel):
    """Configuration for Web Manager."""

    timeout_default: int = Field(default=30)
    allowed_domains: Optional[List[str]] = Field(default=None)


class MCPConfig(BaseModel):
    """MCP Server configuration."""

    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)
    debug: bool = Field(default=False)


class AppConfig(BaseModel):
    """Main application configuration."""

    mcp_host: str = Field(default="127.0.0.1")
    mcp_port: int = Field(default=8000)
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    sandbox_root: str = Field(default=BASE_PATHS["sandbox_root"])
    temp_dir: str = Field(default=BASE_PATHS["temp_dir"])
    
    bash_config: BashConfig = Field(default_factory=BashConfig)
    python_config: PythonConfig = Field(default_factory=PythonConfig)
    filesystem_config: FileSystemConfig = Field(default_factory=FileSystemConfig)
    web_config: WebConfig = Field(default_factory=WebConfig)
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v


def load_env_config() -> Dict[str, Any]:
    """Load configuration from environment variables."""
    config = {}
    
    # MCP Server config
    config["mcp_host"] = os.environ.get("MCP_HOST", "127.0.0.1")
    config["mcp_port"] = int(os.environ.get("MCP_PORT", "8000"))
    config["debug"] = os.environ.get("DEBUG", "false").lower() == "true"
    config["log_level"] = os.environ.get("LOG_LEVEL", "INFO")
    
    # Sandbox config - use env vars if provided, otherwise use detected paths
    config["sandbox_root"] = os.environ.get("SANDBOX_ROOT", BASE_PATHS["sandbox_root"])
    config["temp_dir"] = os.environ.get("TEMP_DIR", BASE_PATHS["temp_dir"])
    
    # Create necessary directory
    os.makedirs(config["sandbox_root"], exist_ok=True)
    os.makedirs(config["temp_dir"], exist_ok=True)
    
    # Bash config
    command_restricted = os.environ.get("COMMAND_RESTRICTED", "true").lower() == "true"
    bash_config = BashConfig(
        sandbox_dir=config["sandbox_root"],
        allowed_commands=os.environ.get("BASH_ALLOWED_COMMANDS", "").split(",") if os.environ.get("BASH_ALLOWED_COMMANDS") else [],
        command_restricted=command_restricted,
        timeout_default=int(os.environ.get("BASH_TIMEOUT_DEFAULT", "30")),
        timeout_max=int(os.environ.get("BASH_TIMEOUT_MAX", "120")),
    )
    config["bash_config"] = bash_config
    
    # Python config
    python_config = PythonConfig(
        sandbox_dir=config["sandbox_root"],
        memory_limit=int(os.environ.get("PYTHON_MEMORY_LIMIT", "256")),
        timeout_default=int(os.environ.get("PYTHON_TIMEOUT_DEFAULT", "30")),
        timeout_max=int(os.environ.get("PYTHON_TIMEOUT_MAX", "120")),
    )
    config["python_config"] = python_config
    
    # File system config
    filesystem_config = FileSystemConfig(
        base_dir=config["sandbox_root"],
        max_file_size_mb=int(os.environ.get("FILE_MAX_SIZE_MB", "10")),
        allowed_extensions=os.environ.get("FILE_ALLOWED_EXTENSIONS", "").split(",") if os.environ.get("FILE_ALLOWED_EXTENSIONS") else [],
    )
    config["filesystem_config"] = filesystem_config
    
    # Web config
    web_domains = os.environ.get("WEB_ALLOWED_DOMAINS", "*")
    web_config = WebConfig(
        timeout_default=int(os.environ.get("WEB_TIMEOUT_DEFAULT", "30")),
        allowed_domains=None if web_domains == "*" else web_domains.split(","),
    )
    config["web_config"] = web_config
    
    return config


def load_config() -> AppConfig:
    """Load configuration from environment variables and validate with Pydantic."""
    try:
        env_config = load_env_config()
        config = AppConfig(**env_config)
        
        # Set logging level
        logging.getLogger().setLevel(config.log_level)
        
        logger.debug("Configuration loaded successfully")
        return config
    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        raise 