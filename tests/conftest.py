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
    # Create a test configuration with safe defaults
    test_config_dict = {
        "mcp_host": "127.0.0.1",
        "mcp_port": 8000,
        "debug": True,
        "log_level": "DEBUG",
        "sandbox_root": "/tmp/cmcp-test-sandbox",
        "temp_dir": "/tmp/cmcp-test-temp",
        "bash_config": {
            "sandbox_dir": "/tmp/cmcp-test-sandbox/bash",
            "allowed_commands": ["ls", "cat", "echo", "pwd"],
            "timeout_default": 5,
            "timeout_max": 10
        },
        "python_config": {
            "sandbox_dir": "/tmp/cmcp-test-sandbox/python",
            "memory_limit": 128,
            "timeout_default": 5,
            "timeout_max": 10
        },
        "filesystem_config": {
            "base_dir": "/tmp/cmcp-test-sandbox/files",
            "max_file_size_mb": 1,
            "allowed_extensions": ["txt", "md", "py", "json"]
        },
        "web_config": {
            "timeout_default": 5,
            "allowed_domains": ["example.com", "google.com"]
        }
    }
    
    # Create config object
    return AppConfig(**test_config_dict)


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


# Helper fixture for asyncio tests
@pytest.fixture
def event_loop():
    """Create an event loop for asyncio tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close() 