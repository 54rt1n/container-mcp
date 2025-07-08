# cmcp/tools/file.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0
"""File tools module.

This module contains tools for file operations like reading, writing, and managing files.
"""

from typing import Dict, Any, Optional
import logging
from mcp.server.fastmcp import FastMCP
from cmcp.managers.file_manager import FileManager, FileMetadata
from cmcp.utils.diff import DiffFormat

logger = logging.getLogger(__name__)

def create_file_tools(mcp: FastMCP, file_manager: FileManager) -> None:
    """Create and register file tools.
    
    Args:
        mcp: The MCP instance
        file_manager: The file manager instance
    """
    @mcp.tool()
    async def fs_read(path: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """Read the contents of a file from the sandbox filesystem.
        
        This tool safely reads any text file within the sandbox environment.
        Returns the file content along with metadata like size and modification time.
        Use this to examine configuration files, source code, or any text documents.
        
        Examples:
        
        Request: {"name": "fs_read", "parameters": {"path": "config.json"}}
        Response: {"content": "{\"name\": \"app\", \"version\": \"1.0\"}", "size": 32, "success": true}
        
        Request: {"name": "fs_read", "parameters": {"path": "logs/app.log", "encoding": "utf-8"}}
        Response: {"content": "2024-01-01 INFO: Application started...", "size": 1024, "success": true}
        """
        try:
            content, metadata = await file_manager.read_file(path, encoding=encoding)
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
    async def fs_write(path: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """Write content to a file in the sandbox filesystem.
        
        This tool creates new files or overwrites existing ones with the provided content.
        The file will be created in the sandbox environment with proper permissions.
        Use this to save configuration files, create scripts, or update documents.
        
        Examples:
        
        Request: {"name": "fs_write", "parameters": {"path": "hello.txt", "content": "Hello, World!"}}
        Response: {"success": true, "path": "hello.txt", "error": null}
        
        Request: {"name": "fs_write", "parameters": {"path": "data/output.json", "content": "{\"result\": \"processed\"}"}}
        Response: {"success": true, "path": "data/output.json", "error": null}
        """
        try:
            success = await file_manager.write_file(path, content, encoding=encoding)
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
    async def fs_list(path: str = "/", pattern: Optional[str] = None, recursive: bool = True) -> Dict[str, Any]:
        """List files and directories in the sandbox filesystem.
        
        This tool provides directory listings with file information including names, sizes, 
        and types. Supports recursive listing and glob pattern filtering.
        Use this to explore the filesystem structure or find specific files.
        
        Examples:
        
        Request: {"name": "fs_list", "parameters": {"path": "/", "recursive": false}}
        Response: {"entries": [{"name": "config.json", "type": "file", "size": 1024}, {"name": "logs", "type": "directory"}], "success": true}
        
        Request: {"name": "fs_list", "parameters": {"path": "src", "pattern": "*.py", "recursive": true}}
        Response: {"entries": [{"name": "main.py", "type": "file", "size": 2048}, {"name": "utils.py", "type": "file", "size": 512}], "success": true}
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
    async def fs_delete(path: str) -> Dict[str, Any]:
        """Delete a file from the sandbox filesystem.
        
        This tool permanently removes a file from the sandbox environment.
        Use with caution as deleted files cannot be recovered.
        Only works on files, not directories.
        
        Examples:
        
        Request: {"name": "fs_delete", "parameters": {"path": "temp.txt"}}
        Response: {"success": true, "path": "temp.txt", "error": null}
        
        Request: {"name": "fs_delete", "parameters": {"path": "cache/old_data.json"}}
        Response: {"success": true, "path": "cache/old_data.json", "error": null}
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
    async def fs_move(source_path: str, destination_path: str) -> Dict[str, Any]:
        """Move or rename a file in the sandbox filesystem.
        
        This tool relocates a file from one path to another within the sandbox.
        Can be used for both moving files to different directories and renaming files.
        The destination directory must exist or the operation will fail.
        
        Examples:
        
        Request: {"name": "fs_move", "parameters": {"source_path": "draft.txt", "destination_path": "final.txt"}}
        Response: {"success": true, "source_path": "draft.txt", "destination_path": "final.txt", "error": null}
        
        Request: {"name": "fs_move", "parameters": {"source_path": "temp/data.json", "destination_path": "archive/backup_data.json"}}
        Response: {"success": true, "source_path": "temp/data.json", "destination_path": "archive/backup_data.json", "error": null}
        """
        try:
            success = await file_manager.move_file(source_path, destination_path)
            return {
                "success": success,
                "source_path": source_path,
                "destination_path": destination_path,
                "error": None
            }
        except Exception as e:
            logger.warning(f"Error moving file {source_path} to {destination_path}: {str(e)}")
            return {
                "success": False,
                "source_path": source_path,
                "destination_path": destination_path,
                "error": str(e)
            }
    
    @mcp.tool()
    async def fs_apply_diff(path: str, diff: str) -> Dict[str, Any]:
        """Apply a unified diff patch to a file in the sandbox filesystem.
        
        This tool applies a unified diff (patch) to modify an existing file.
        The diff should be in standard unified diff format with proper line context.
        Use this for making precise changes to files when you have the exact diff.
        
        Examples:
        
        Request: {"name": "fs_apply_diff", "parameters": {"path": "config.py", "diff": "--- a/config.py\\n+++ b/config.py\\n@@ -1,3 +1,3 @@\\n-DEBUG = False\\n+DEBUG = True\\n PORT = 8080"}}
        Response: {"success": true, "path": "config.py", "lines_applied": 1, "new_size": 245}
        
        Request: {"name": "fs_apply_diff", "parameters": {"path": "README.md", "diff": "--- a/README.md\\n+++ b/README.md\\n@@ -5,4 +5,5 @@\\n ## Features\\n - Fast\\n - Secure\\n+- Reliable"}}
        Response: {"success": true, "path": "README.md", "lines_applied": 1, "new_size": 512}
        """
        try:
            result = await file_manager.apply_diff_to_file(path, diff)
            return result
        except Exception as e:
            logger.warning(f"Error applying diff to file {path}: {str(e)}")
            return {
                "success": False,
                "path": path,
                "lines_applied": 0,
                "new_size": 0,
                "error": str(e)
            }
    
    # Register file resource handler
    @mcp.resource("fs://{path}")
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