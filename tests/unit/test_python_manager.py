# tests/unit/test_python_manager.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Unit tests for PythonManager."""

import os
import pytest
import asyncio

from cmcp.managers.python_manager import PythonManager


@pytest.mark.asyncio
async def test_basic_code_execution(python_manager):
    """Test basic Python code execution."""
    # Test simple print
    result = await python_manager.execute("print('hello world')")
    assert result.output.strip() == "hello world"
    assert result.error == ""
    assert result.result is None

    # Test with a return value
    result = await python_manager.execute("_ = 42")
    assert result.output == ""
    assert result.error == ""
    assert result.result == 42

    # Test with some computation
    result = await python_manager.execute("""
import math
result = 0
for i in range(5):
    result += i * math.pi
_ = result
""")
    assert result.error == ""
    assert isinstance(result.result, float)
    assert abs(result.result - (0 + 1*3.14159 + 2*3.14159 + 3*3.14159 + 4*3.14159)) < 0.01


@pytest.mark.asyncio
async def test_code_timeout(python_manager):
    """Test code execution timeout."""
    # Test code that should timeout
    result = await python_manager.execute("""
import time
time.sleep(10)
""", timeout=1)
    assert "timed out" in result.error


@pytest.mark.asyncio
async def test_exception_handling(python_manager):
    """Test exception handling in Python code."""
    # Test code with a syntax error
    result = await python_manager.execute("print('incomplete")
    assert "SyntaxError" in result.error

    # Test code with a runtime error
    result = await python_manager.execute("""
def divide_by_zero():
    return 1/0

divide_by_zero()
""")
    assert "ZeroDivisionError" in result.error


@pytest.mark.asyncio
async def test_memory_limit(python_manager):
    """Test memory limit enforcement."""
    # This test might be flaky depending on environment
    # Test with a large array that should exceed memory limit
    result = await python_manager.execute("""
# Try to allocate a large array
large_array = [0] * (1024 * 1024 * 200)  # 200MB
_ = len(large_array)
""")
    # Either the code fails with a memory error or it succeeds but is terminated
    assert result.result is None or "MemoryError" in result.error


@pytest.mark.asyncio
async def test_from_env_initialization(test_config):
    """Test .from_env() initialization."""
    # Mock the config loader to return our test config
    import cmcp.config
    original_load_config = cmcp.config.load_config
    cmcp.config.load_config = lambda: test_config

    try:
        # Initialize from environment
        manager = PythonManager.from_env()
        
        # Verify the manager was initialized correctly
        assert manager.sandbox_dir == test_config.python_config.sandbox_dir
        assert manager.memory_limit == test_config.python_config.memory_limit
        assert manager.timeout_default == test_config.python_config.timeout_default
        assert manager.timeout_max == test_config.python_config.timeout_max
    finally:
        # Restore the original function
        cmcp.config.load_config = original_load_config 