# cmcp/tools/file.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0
"""File tools module.

This module contains tools for file operations like reading, writing, and managing files.
"""

from typing import Dict, Any, Optional
import logging
from mcp.server.fastmcp import FastMCP
from cmcp.managers.file_manager import FileManager, FileMetadata

logger = logging.getLogger(__name__)

def create_file_tools(mcp: FastMCP, file_manager: FileManager) -> None:
    """Create and register file tools.
    
    Args:
        mcp: The MCP instance
        file_manager: The file manager instance
    """
    @mcp.tool()
    async def file_read(path: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """Read file contents safely.
        
        Args:
            path: Path to the file (relative to sandbox root)
            encoding: File encoding
            
        Returns:
            Dictionary containing file content and metadata
        """
        try:
            content, metadata = await file_manager.read_file(path)
            return {
                "content": content,
                "size": metadata.size,
                "modified": metadata.modified_time,
                "success": True,
                "error": None
            }
        except Exception as e:
            logger.warning(f"Error reading file {path}: {str(e)}")
            return {
                "content": "",
                "size": 0,
                "modified": "",
                "success": False,
                "error": str(e)
            }
    
    @mcp.tool()
    async def file_write(path: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """Write content to a file safely.
        
        Args:
            path: Path to the file (relative to sandbox root)
            content: Content to write
            encoding: File encoding
            
        Returns:
            Dictionary containing success status and file path
        """
        try:
            success = await file_manager.write_file(path, content)
            return {
                "success": success,
                "path": path,
                "error": None
            }
        except Exception as e:
            logger.warning(f"Error writing file {path}: {str(e)}")
            return {
                "success": False,
                "path": path,
                "error": str(e)
            }
    
    @mcp.tool()
    async def file_list(path: str = "/", pattern: Optional[str] = None, recursive: bool = True) -> Dict[str, Any]:
        """List contents of a directory safely.
        
        Args:
            path: Path to the directory (relative to sandbox root)
            pattern: Optional glob pattern to filter files
            recursive: Whether to list files recursively (default: True)
            
        Returns:
            Dictionary containing directory entries
        """
        try:
            entries = await file_manager.list_directory(path, recursive=recursive)
            
            # Apply pattern filtering if specified
            if pattern:
                import fnmatch
                entries = [entry for entry in entries if fnmatch.fnmatch(entry["name"], pattern)]
                
            return {
                "entries": entries,
                "path": path,
                "success": True,
                "error": None
            }
        except Exception as e:
            logger.warning(f"Error listing directory {path}: {str(e)}")
            return {
                "entries": [],
                "path": path,
                "success": False,
                "error": str(e)
            }
    
    @mcp.tool()
    async def file_delete(path: str) -> Dict[str, Any]:
        """Delete a file safely.
        
        Args:
            path: Path of the file to delete
            
        Returns:
            Dictionary containing success status and path
        """
        try:
            success = await file_manager.delete_file(path)
            return {
                "success": success,
                "path": path,
                "error": None
            }
        except Exception as e:
            logger.warning(f"Error deleting file {path}: {str(e)}")
            return {
                "success": False,
                "path": path,
                "error": str(e)
            }
    
    @mcp.tool()
    async def file_move(source: str, destination: str) -> Dict[str, Any]:
        """Move or rename a file safely.
        
        Args:
            source: Source file path
            destination: Destination file path
            
        Returns:
            Dictionary containing success status, source and destination
        """
        try:
            success = await file_manager.move_file(source, destination)
            return {
                "success": success,
                "source": source,
                "destination": destination,
                "error": None
            }
        except Exception as e:
            logger.warning(f"Error moving file {source} to {destination}: {str(e)}")
            return {
                "success": False,
                "source": source,
                "destination": destination,
                "error": str(e)
            }
    
    # Register file resource handler
    @mcp.resource("file://{path}")
    async def get_file(path: str) -> str:
        """Get file contents as a resource.
        
        Args:
            path: Path to the file (relative to sandbox root)
            
        Returns:
            File contents
        """
        try:
            content, _ = await file_manager.read_file(path)
            return content
        except Exception as e:
            logger.error(f"Error accessing file resource {path}: {str(e)}")
            return f"Error: {str(e)}" 