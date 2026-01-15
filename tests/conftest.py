# tests/conftest.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Configuration file for pytest."""

import os
import pytest
import tempfile
import shutil
import asyncio
from typing import Dict, Any

from cmcp.config import AppConfig
from cmcp.managers.bash_manager import BashManager
from cmcp.managers.python_manager import PythonManager
from cmcp.managers.file_manager import FileManager
from cmcp.managers.web_manager import WebManager


@pytest.fixture
def test_config() -> AppConfig:
    """Create a test configuration object."""
    # Create a temporary base directory for this test run
    with tempfile.TemporaryDirectory(prefix="cmcp-test-base-") as temp_base_dir:
        sandbox_root = os.path.join(temp_base_dir, "sandbox")
        temp_dir_files = os.path.join(temp_base_dir, "temp")
        kb_storage = os.path.join(temp_base_dir, "kb")
        sparse_idx_path = os.path.join(kb_storage, "search/sparse_idx")
        graph_idx_path = os.path.join(kb_storage, "search/graph_idx")

        # Create necessary dirs for config loading
        os.makedirs(sandbox_root, exist_ok=True)
        os.makedirs(temp_dir_files, exist_ok=True)
        os.makedirs(kb_storage, exist_ok=True)
        os.makedirs(sparse_idx_path, exist_ok=True)
        os.makedirs(graph_idx_path, exist_ok=True)

        test_config_dict = {
            "mcp_host": "127.0.0.1",
            "mcp_port": 8000,
            "debug": True,
            "log_level": "DEBUG",
            "sandbox_root": sandbox_root,
            "temp_dir": temp_dir_files,
            "bash_config": {
                "sandbox_dir": os.path.join(sandbox_root, "bash"), # Use subdirs
                "allowed_commands": ["ls", "cat", "echo", "pwd"],
                "timeout_default": 5,
                "timeout_max": 10
            },
            "python_config": {
                "sandbox_dir": os.path.join(sandbox_root, "python"), # Use subdirs
                "memory_limit": 128,
                "timeout_default": 5,
                "timeout_max": 10
            },
            "filesystem_config": {
                "base_dir": os.path.join(sandbox_root, "files"), # Use subdirs
                "max_file_size_mb": 1,
                "allowed_extensions": ["txt", "md", "py", "json"]
            },
            "web_config": {
                "timeout_default": 5,
                "allowed_domains": ["example.com", "google.com"],
                "brave_search_api_key": "dummy_key" # Add dummy key if needed
            },
            # --- Add/Update KB Config ---
            "kb_config": {
                "storage_path": kb_storage,
                "timeout_default": 30,
                "timeout_max": 60,
                "search_enabled": True, # Default for testing manager logic
                "sparse_index_path": sparse_idx_path,
                "graph_index_path": graph_idx_path,
                "reranker_model": "mixedbread-ai/mxbai-rerank-base-v1", # Keep model name
                "search_relation_predicates": ["references", "cites"], # Example list
                "search_graph_neighbor_limit": 500 # Example limit
            },
            # --- End KB Config ---
            # --- Add List Config ---
            "list_config": {
                "storage_path": os.path.join(temp_base_dir, "lists")
            },
            # --- End List Config ---
            # Market config
            "market_config": {
                "timeout_default": 5,
                "timeout_max": 10
            },
            # RSS config
            "rss_config": {
                "timeout_default": 5,
                "timeout_max": 10,
                "user_agent": "test-agent/1.0"
            }
        }

        # Create config object
        yield AppConfig(**test_config_dict)
        # temp_base_dir is cleaned up automatically by TemporaryDirectory context manager


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp(prefix="cmcp-test-")
    yield temp_dir
    
    # Clean up after test
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def bash_manager(test_config):
    """Create a BashManager instance for tests."""
    # Create sandbox directory
    os.makedirs(test_config.bash_config.sandbox_dir, exist_ok=True)
    
    # Create manager
    manager = BashManager(
        sandbox_dir=test_config.bash_config.sandbox_dir,
        allowed_commands=test_config.bash_config.allowed_commands,
        timeout_default=test_config.bash_config.timeout_default,
        timeout_max=test_config.bash_config.timeout_max
    )
    
    yield manager


@pytest.fixture
def python_manager(test_config):
    """Create a PythonManager instance for tests."""
    # Create sandbox directory
    os.makedirs(test_config.python_config.sandbox_dir, exist_ok=True)
    
    # Create manager
    manager = PythonManager(
        sandbox_dir=test_config.python_config.sandbox_dir,
        memory_limit=test_config.python_config.memory_limit,
        timeout_default=test_config.python_config.timeout_default,
        timeout_max=test_config.python_config.timeout_max
    )
    
    yield manager


@pytest.fixture
def file_manager(test_config):
    """Create a FileManager instance for tests."""
    # Create sandbox directory
    os.makedirs(test_config.filesystem_config.base_dir, exist_ok=True)
    
    # Create manager
    manager = FileManager(
        base_dir=test_config.filesystem_config.base_dir,
        max_file_size_mb=test_config.filesystem_config.max_file_size_mb,
        allowed_extensions=test_config.filesystem_config.allowed_extensions
    )
    
    yield manager


@pytest.fixture
def web_manager(test_config):
    """Create a WebManager instance for tests."""
    # Create manager
    manager = WebManager(
        timeout_default=test_config.web_config.timeout_default,
        allowed_domains=test_config.web_config.allowed_domains
    )
    
    yield manager


@pytest.fixture
def list_manager(test_config):
    """Create a ListManager instance for tests."""
    # Import here to avoid circular imports
    from cmcp.managers.list_manager import ListManager
    
    # Create storage directory
    os.makedirs(test_config.list_config.storage_path, exist_ok=True)
    
    # Create manager
    manager = ListManager(storage_path=test_config.list_config.storage_path)
    
    yield manager


@pytest.fixture
async def kb_manager(test_config):
    """Create a KnowledgeBaseManager instance for tests."""
    # Import here to avoid circular imports
    from cmcp.managers import KnowledgeBaseManager

    # Create manager
    manager = KnowledgeBaseManager.from_env(test_config)
    # Initialize the manager
    await manager.initialize()

    yield manager


@pytest.fixture
def market_manager(test_config):
    """Create a MarketManager instance for tests."""
    from cmcp.managers.market_manager import MarketManager

    manager = MarketManager(
        timeout_default=test_config.market_config.timeout_default,
        timeout_max=test_config.market_config.timeout_max
    )
    yield manager


@pytest.fixture
def rss_manager(test_config):
    """Create an RssManager instance for tests."""
    from cmcp.managers.rss_manager import RssManager

    manager = RssManager(
        timeout_default=test_config.rss_config.timeout_default,
        timeout_max=test_config.rss_config.timeout_max,
        user_agent=test_config.rss_config.user_agent
    )
    yield manager