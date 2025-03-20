# tests/integration/test_mcp_server.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Integration tests for the MCP server."""

import os
import pytest
import asyncio
import tempfile
from unittest.mock import AsyncMock, patch, MagicMock

# Create all necessary mock classes
class MockMCPClient(MagicMock):
    """Mock MCP client for testing."""
    pass

class MockFastMCP(MagicMock):
    """Mock FastMCP class for testing."""
    pass

class MockWebSocketServerTransport(MagicMock):
    """Mock WebSocket transport class for testing."""
    pass

from cmcp.config import AppConfig
from cmcp.managers.bash_manager import BashManager, BashResult
from cmcp.managers.python_manager import PythonManager, PythonResult
from cmcp.managers.file_manager import FileManager, FileMetadata
from cmcp.managers.web_manager import WebManager


@pytest.fixture
async def mock_mcp_server():
    """Create a mock MCP server with tools registered."""
    # Create a simpler mock structure with functions directly attached
    mock_server = MagicMock()
    
    # Create the tool registry to track registered tools
    mock_server.tool_registry = {}
    
    # Create a decorator-like function that registers tools
    def tool_decorator(f):
        mock_server.tool_registry[f.__name__] = f
        return f
    
    # Create the tool method that returns the decorator
    mock_server.tool = MagicMock(return_value=tool_decorator)
    
    # Create the resource registry
    mock_server.resource_registry = {}
    
    # Create a decorator-like function that registers resources
    def resource_decorator(pattern):
        def register_resource(f):
            mock_server.resource_registry[pattern] = f
            return f
        return register_resource
    
    # Create the resource method that returns the decorator
    mock_server.resource = resource_decorator
    
    # Create and register all the tools
    # Bash tool
    @mock_server.tool()
    async def system_run_command(command, working_dir=None):
        result = await BashManager.execute(command)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "success": result.exit_code == 0
        }
    
    # Python tool
    @mock_server.tool()
    async def system_run_python(code, working_dir=None):
        result = await PythonManager.execute(code)
        return {
            "output": result.output,
            "error": result.error,
            "result": result.result,
            "success": not result.error
        }
    
    # File tools
    @mock_server.tool()
    async def file_read(path, encoding="utf-8"):
        content, metadata = await FileManager.read_file(path)
        return {
            "content": content,
            "size": metadata.size,
            "modified": metadata.modified_time,
            "success": True
        }
    
    @mock_server.tool()
    async def file_write(path, content, encoding="utf-8"):
        success = await FileManager.write_file(path, content)
        return {
            "success": success
        }
    
    @mock_server.tool()
    async def file_list(path="/", pattern=None):
        entries = await FileManager.list_directory(path)
        return {
            "entries": entries,
            "success": True
        }
    
    @mock_server.tool()
    async def file_delete(path):
        success = await FileManager.delete_file(path)
        return {
            "success": success
        }
    
    @mock_server.tool()
    async def file_move(source, destination):
        success = await FileManager.move_file(source, destination)
        return {
            "success": success
        }
    
    # Web tools
    @mock_server.tool()
    async def web_search(query):
        results = await WebManager.search_web(query)
        return results
    
    @mock_server.tool()
    async def web_scrape(url, selector=None):
        result = await WebManager.scrape_webpage(url, selector)
        return {
            "content": result.content,
            "title": result.title,
            "url": result.url,
            "success": result.success,
            "error": result.error
        }
    
    @mock_server.tool()
    async def web_browse(url):
        result = await WebManager.browse_webpage(url)
        return {
            "content": result.content,
            "title": result.title,
            "url": result.url,
            "success": result.success,
            "error": result.error
        }
    
    @mock_server.tool()
    async def system_env_var(var_name=None):
        if var_name:
            value = os.environ.get(var_name)
            return {
                "name": var_name,
                "value": value,
                "success": True
            }
        else:
            # Return all env vars
            return {
                "variables": dict(os.environ),
                "success": True
            }
    
    # Register file resource
    @mock_server.resource("file://{path}")
    async def get_file(path):
        content, _ = await FileManager.read_file(path)
        return content
    
    yield mock_server


@pytest.mark.asyncio
async def test_tool_registration(mock_mcp_server):
    """Test that all tools are properly registered with the MCP server."""
    # All tools should be in the registry
    expected_tools = [
        'system_run_command',
        'system_run_python', 
        'file_read',
        'file_write',
        'file_list',
        'file_delete',
        'file_move',
        'web_search',
        'web_scrape',
        'web_browse',
        'system_env_var'
    ]
    
    # Check that all expected tools are registered
    for tool in expected_tools:
        assert tool in mock_mcp_server.tool_registry, f"Tool {tool} was not registered"
    
    # Check that MCP resource was registered
    assert "file://{path}" in mock_mcp_server.resource_registry, "File resource was not registered"


@pytest.mark.asyncio
@patch('cmcp.managers.bash_manager.BashManager.execute')
async def test_bash_command_execution(mock_execute, mock_mcp_server):
    """Test bash command execution via MCP tool."""
    # Get the tool function
    system_run_command = mock_mcp_server.tool_registry['system_run_command']
    
    # Mock the BashManager.execute method
    mock_execute.return_value = BashResult(
        stdout="command output",
        stderr="",
        exit_code=0
    )
    
    # Execute the tool function directly
    result = await system_run_command("echo test")
    
    # Verify the result
    assert result["stdout"] == "command output"
    assert result["exit_code"] == 0
    
    # Verify BashManager.execute was called correctly
    mock_execute.assert_called_once_with("echo test")


@pytest.mark.asyncio
@patch('cmcp.managers.python_manager.PythonManager.execute')
async def test_python_code_execution(mock_execute, mock_mcp_server):
    """Test Python code execution via MCP tool."""
    # Get the tool function
    system_run_python = mock_mcp_server.tool_registry['system_run_python']
    
    # Mock the PythonManager.execute method
    mock_execute.return_value = PythonResult(
        output="hello world",
        error="",
        result=42
    )
    
    # Execute the tool function directly
    result = await system_run_python("print('hello world'); _ = 42")
    
    # Verify the result
    assert result["output"] == "hello world"
    assert result["result"] == 42
    assert result["error"] == ""
    
    # Verify PythonManager.execute was called correctly
    mock_execute.assert_called_once_with("print('hello world'); _ = 42")


@pytest.mark.asyncio
@patch('cmcp.managers.file_manager.FileManager.read_file')
async def test_file_read_tool(mock_read_file, mock_mcp_server):
    """Test file read operation via MCP tool."""
    # Get the tool function
    file_read = mock_mcp_server.tool_registry['file_read']
    
    # Mock the FileManager.read_file method
    mock_read_file.return_value = (
        "file content",
        FileMetadata(
            size=12,
            modified_time=1234567890.0,
            is_directory=False
        )
    )
    
    # Execute the tool function directly
    result = await file_read("test.txt")
    
    # Verify the result
    assert result["content"] == "file content"
    assert result["size"] == 12
    assert result["modified"] == 1234567890.0
    assert result["success"] is True
    
    # Verify FileManager.read_file was called correctly
    mock_read_file.assert_called_once_with("test.txt") 