# cmcp/config.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Configuration module for Container-MCP."""

import os
import logging
import tempfile
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator

# Configure logging
logger = logging.getLogger(__name__)


# Detect environment
def is_in_container() -> bool:
    """Check if we're running inside a container."""
    return os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv') or os.environ.get("CONTAINER") == "true"


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
    brave_search_api_key: Optional[str] = Field(default=None, description="API Key for Brave Search API")


class KBConfig(BaseModel):
    """Configuration for Knowledge Base Manager."""
    
    storage_path: str = Field(default=os.path.join(BASE_PATHS["base_dir"], "kb"))
    timeout_default: int = Field(default=30)
    timeout_max: int = Field(default=120)
    # Search configuration
    search_enabled: bool = Field(default=True, description="Enable search functionality")
    sparse_index_path: Optional[str] = Field(default=None, description="Path to sparse search index")
    graph_index_path: Optional[str] = Field(default=None, description="Path to graph search index")
    reranker_model: Optional[str] = Field(default="mixedbread-ai/mxbai-rerank-base-v1", description="Reranker model name")
    search_relation_predicates: List[str] = Field(default_factory=lambda: ["references"], description="Relation predicates to follow in graph search")
    search_graph_neighbor_limit: int = Field(default=1000, description="Maximum number of neighbors to retrieve in graph search")


class ListConfig(BaseModel):
    """Configuration for List Manager."""

    storage_path: str = Field(default=os.path.join(BASE_PATHS["base_dir"], "lists"))


class MarketConfig(BaseModel):
    """Configuration for Market Manager."""
    timeout_default: int = Field(default=30)
    timeout_max: int = Field(default=60)


class RssConfig(BaseModel):
    """Configuration for RSS Manager."""
    timeout_default: int = Field(default=15)
    timeout_max: int = Field(default=30)
    user_agent: str = Field(default="container-mcp/1.0")


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
    kb_config: KBConfig = Field(default_factory=KBConfig)
    list_config: ListConfig = Field(default_factory=ListConfig)
    market_config: MarketConfig = Field(default_factory=MarketConfig)
    rss_config: RssConfig = Field(default_factory=RssConfig)

    # Tool Enable/Disable Flags
    tools_enable_system: bool = Field(default=True, description="Enable System tools (bash, python)")
    tools_enable_file: bool = Field(default=True, description="Enable File tools")
    tools_enable_web: bool = Field(default=True, description="Enable Web tools (search, scrape, browse)")
    tools_enable_kb: bool = Field(default=True, description="Enable Knowledge Base tools")
    tools_enable_list: bool = Field(default=True, description="Enable List tools")
    tools_enable_market: bool = Field(default=True, description="Enable Market tools")
    tools_enable_rss: bool = Field(default=True, description="Enable RSS tools")
    
    @field_validator("log_level")
    @classmethod
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
    config["base_dir"] = os.environ.get("BASE_DIR", BASE_PATHS["base_dir"])
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
    brave_key = os.environ.get("BRAVE_SEARCH_API_KEY")  # Get the key from env
    web_config = WebConfig(
        timeout_default=int(os.environ.get("WEB_TIMEOUT_DEFAULT", "30")),
        allowed_domains=None if web_domains == "*" else web_domains.split(","),
        brave_search_api_key=brave_key  # Pass the retrieved key
    )
    config["web_config"] = web_config
    
    # Knowledge Base config
    kb_storage_path = os.environ.get("CMCP_KB_STORAGE_PATH", os.path.join(config["base_dir"], "kb"))
    kb_config = KBConfig(
        storage_path=kb_storage_path,
        timeout_default=int(os.environ.get("KB_TIMEOUT_DEFAULT", "30")),
        timeout_max=int(os.environ.get("KB_TIMEOUT_MAX", "120")),
        # Search configuration
        search_enabled=os.environ.get("CMCP_KB_SEARCH_ENABLED", "true").lower() == "true",
        sparse_index_path=os.environ.get("CMCP_KB_SPARSE_INDEX_PATH", os.path.join(kb_storage_path, "search/sparse_idx")),
        graph_index_path=os.environ.get("CMCP_KB_GRAPH_INDEX_PATH", os.path.join(kb_storage_path, "search/graph_idx")),
        reranker_model=os.environ.get("CMCP_KB_RERANKER_MODEL", "mixedbread-ai/mxbai-rerank-base-v1"),
        search_relation_predicates=os.environ.get("CMCP_KB_SEARCH_RELATION_PREDICATES", "references").split(",") if os.environ.get("CMCP_KB_SEARCH_RELATION_PREDICATES") else ["references"],
        search_graph_neighbor_limit=int(os.environ.get("CMCP_KB_SEARCH_GRAPH_NEIGHBOR_LIMIT", "1000"))
    )
    config["kb_config"] = kb_config
    
    # List config
    list_storage_path = os.environ.get("CMCP_LIST_STORAGE_PATH", os.path.join(config["base_dir"], "lists"))
    list_config = ListConfig(
        storage_path=list_storage_path
    )
    config["list_config"] = list_config
    
    # Market config
    market_config = MarketConfig(
        timeout_default=int(os.environ.get("MARKET_TIMEOUT_DEFAULT", "30")),
        timeout_max=int(os.environ.get("MARKET_TIMEOUT_MAX", "60")),
    )
    config["market_config"] = market_config

    # RSS config
    rss_config = RssConfig(
        timeout_default=int(os.environ.get("RSS_TIMEOUT_DEFAULT", "15")),
        timeout_max=int(os.environ.get("RSS_TIMEOUT_MAX", "30")),
        user_agent=os.environ.get("RSS_USER_AGENT", "container-mcp/1.0"),
    )
    config["rss_config"] = rss_config

    # Tool Enable/Disable Flags - default to true if not set
    config["tools_enable_system"] = os.environ.get("TOOLS_ENABLE_SYSTEM", "true").lower() == "true"
    config["tools_enable_file"] = os.environ.get("TOOLS_ENABLE_FILE", "true").lower() == "true"
    config["tools_enable_web"] = os.environ.get("TOOLS_ENABLE_WEB", "true").lower() == "true"
    config["tools_enable_kb"] = os.environ.get("TOOLS_ENABLE_KB", "true").lower() == "true"
    config["tools_enable_list"] = os.environ.get("TOOLS_ENABLE_LIST", "true").lower() == "true"
    config["tools_enable_market"] = os.environ.get("TOOLS_ENABLE_MARKET", "true").lower() == "true"
    config["tools_enable_rss"] = os.environ.get("TOOLS_ENABLE_RSS", "true").lower() == "true"

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