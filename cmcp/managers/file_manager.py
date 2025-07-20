# cmcp/managers/file_manager.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""File Manager for secure file operations."""

import os
import aiofiles
from typing import List, Dict, Any, Tuple, Optional

from cmcp.types.file import FileMetadata
from cmcp.utils.logging import get_logger
from cmcp.utils.io import read_file, write_file
from cmcp.utils.diff import generate_diff, apply_unified_diff, split_patch_into_files, analyze_diff, DiffFormat

logger = get_logger(__name__)


class FileManager:
    """Manager for secure file operations."""
    
    def __init__(
        self,
        base_dir: str,
        max_file_size_mb: int = 10,
        allowed_extensions: List[str] = None,
        command_restricted: bool = True
    ):
        """Initialize the FileManager.
        
        Args:
            base_dir: Base directory for file operations
            max_file_size_mb: Maximum file size in MB
            allowed_extensions: List of allowed file extensions
            command_restricted: Whether to restrict file extensions to allowed list
        """
        self.base_dir = base_dir
        self.max_file_size_mb = max_file_size_mb
        self.allowed_extensions = allowed_extensions or ["txt", "md", "csv", "json", "py", "sh"]
        self.command_restricted = command_restricted
        
        # Ensure base directory exists
        os.makedirs(self.base_dir, exist_ok=True)
        logger.debug(f"FileManager initialized with base dir at {self.base_dir}")
        logger.debug(f"Command restriction {'enabled' if command_restricted else 'disabled'}")
        if command_restricted:
            logger.debug(f"Allowed extensions: {', '.join(self.allowed_extensions)}")
    
    @classmethod
    def from_env(cls, config=None):
        """Create a FileManager from environment configuration.
        
        Args:
            config: Optional configuration object, loads from environment if not provided
            
        Returns:
            Configured FileManager instance
        """
        if config is None:
            from cmcp.config import load_config
            config = load_config()
        
        logger.debug("Creating FileManager from environment configuration")
        return cls(
            base_dir=config.filesystem_config.base_dir,
            max_file_size_mb=config.filesystem_config.max_file_size_mb,
            allowed_extensions=config.filesystem_config.allowed_extensions,
            command_restricted=config.bash_config.command_restricted
        )
    
    def _validate_path(self, path: str) -> str:
        """Validate and normalize a file path to prevent escaping the sandbox.
        
        Args:
            path: Path to validate
            
        Returns:
            Normalized absolute path
            
        Raises:
            ValueError: If path traversal is detected
        """
        # Remove leading slash if present to make path relative
        path = path.lstrip("/")
        
        # Normalize the path
        norm_path = os.path.normpath(os.path.join(self.base_dir, path))
        
        # Check for path traversal attempts
        if not norm_path.startswith(self.base_dir):
            logger.warning(f"Path traversal attempt detected: {path}")
            raise ValueError(f"Path traversal attempt detected: {path}")
        
        return norm_path
    
    def _validate_extension(self, path: str) -> None:
        """Validate file extension is allowed.
        
        Args:
            path: Path to validate
            
        Raises:
            ValueError: If extension is not allowed
        """
        # Skip validation if command restrictions are disabled
        if not self.command_restricted:
            logger.debug(f"Command restrictions disabled, skipping extension validation for: {path}")
            return
            
        ext = os.path.splitext(path)[1].lstrip(".")
        if ext and ext not in self.allowed_extensions:
            logger.warning(f"File extension not allowed: {ext}")
            raise ValueError(f"File extension not allowed: {ext}")
    
    async def read_file(self, path: str, encoding: str = "utf-8") -> Tuple[str, FileMetadata]:
        """Read a file's contents safely.
        
        Args:
            path: Path to the file (relative to base_dir)
            
        Returns:
            Tuple of (file content, file metadata)
            
        Raises:
            FileNotFoundError: If file doesn't exist
            IsADirectoryError: If path is a directory
            ValueError: If file too large or extension not allowed
        """
        # Validate the path
        full_path = self._validate_path(path)
        
        # Check if file exists
        if not os.path.exists(full_path):
            logger.warning(f"File not found: {path}")
            raise FileNotFoundError(f"File not found: {path}")
        
        # Validate the file is not a directory
        if os.path.isdir(full_path):
            logger.warning(f"Path is a directory: {path}")
            raise IsADirectoryError(f"Path is a directory: {path}")
        
        # Validate extension
        self._validate_extension(path)
        
        # Read the file
        content, metadata = await read_file(full_path, self.max_file_size_mb, encoding)
        
        return content, metadata
    
    async def write_file(self, path: str, content: str, encoding: str = "utf-8") -> bool:
        """Write content to a file safely.
        
        Args:
            path: Path to the file (relative to base_dir)
            content: Content to write
            
        Returns:
            True if write was successful
            
        Raises:
            ValueError: If content too large or extension not allowed
        """
        # Validate the path
        full_path = self._validate_path(path)
        
        # Validate extension
        self._validate_extension(path)
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Check content size
        content_size = len(content.encode('utf-8'))
        if content_size > self.max_file_size_mb * 1024 * 1024:
            logger.warning(f"Content too large: {content_size} bytes")
            raise ValueError(f"Content too large: {content_size} bytes (maximum {self.max_file_size_mb} MB)")
        
        # Write the file
        logger.debug(f"Writing file: {path}")
        await write_file(full_path, content, encoding=encoding)
        
        return True
    
    async def list_directory(self, path: str = "/", recursive: bool = True) -> List[Dict[str, Any]]:
        """List contents of a directory safely.
        
        Args:
            path: Path to the directory (relative to base_dir)
            recursive: Whether to list files recursively (default: True)
            
        Returns:
            List of directory entries with metadata
            
        Raises:
            FileNotFoundError: If path doesn't exist
            NotADirectoryError: If path is not a directory
        """
        # Validate the path
        full_path = self._validate_path(path)
        
        # Check if path exists
        if not os.path.exists(full_path):
            logger.warning(f"Path not found: {path}")
            raise FileNotFoundError(f"Path not found: {path}")
        
        # Validate the path is a directory
        if not os.path.isdir(full_path):
            logger.warning(f"Path is not a directory: {path}")
            raise NotADirectoryError(f"Path is not a directory: {path}")
        
        # List the directory
        logger.debug(f"Listing directory: {path} (recursive={recursive})")
        entries = []
        
        # Directories to skip during recursive listing
        skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv'}
        
        if recursive:
            # Walk the directory tree recursively
            for root, dirs, files in os.walk(full_path):
                # Remove directories we want to skip from the dirs list
                # This modifies dirs in place and prevents os.walk from recursing into them
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                
                # Process all files in current directory
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, self.base_dir)
                    # Replace backslashes with forward slashes for consistency
                    rel_path = rel_path.replace('\\', '/')
                    
                    entries.append({
                        "name": file,
                        "path": rel_path,
                        "is_directory": False,
                        "size": os.path.getsize(file_path),
                        "modified": os.path.getmtime(file_path)
                    })
                
                # Process all directories in current directory
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    rel_path = os.path.relpath(dir_path, self.base_dir)
                    # Replace backslashes with forward slashes for consistency
                    rel_path = rel_path.replace('\\', '/')
                    
                    entries.append({
                        "name": dir_name,
                        "path": rel_path,
                        "is_directory": True,
                        "size": None,
                        "modified": os.path.getmtime(dir_path)
                    })
        else:
            # Non-recursive listing (original behavior)
            for entry in os.scandir(full_path):
                # Create relative path from base dir
                rel_path = os.path.relpath(entry.path, self.base_dir)
                
                # Replace backslashes with forward slashes for consistency
                rel_path = rel_path.replace('\\', '/')
                
                entries.append({
                    "name": entry.name,
                    "path": rel_path,
                    "is_directory": entry.is_dir(),
                    "size": entry.stat().st_size if entry.is_file() else None,
                    "modified": entry.stat().st_mtime
                })
        
        return entries
    
    async def delete_file(self, path: str) -> bool:
        """Delete a file safely.
        
        Args:
            path: Path to the file (relative to base_dir)
            
        Returns:
            True if deletion was successful
            
        Raises:
            FileNotFoundError: If file doesn't exist
            IsADirectoryError: If path is a directory
        """
        # Validate the path
        full_path = self._validate_path(path)
        
        # Check if file exists
        if not os.path.exists(full_path):
            logger.warning(f"File not found: {path}")
            raise FileNotFoundError(f"File not found: {path}")
        
        # Validate the file is not a directory
        if os.path.isdir(full_path):
            logger.warning(f"Path is a directory: {path}")
            raise IsADirectoryError(f"Cannot delete directory: {path}")
        
        # Delete the file
        logger.debug(f"Deleting file: {path}")
        os.unlink(full_path)
        
        return True
    
    async def move_file(self, source: str, destination: str) -> bool:
        """Move or rename a file safely.
        
        Args:
            source: Source path (relative to base_dir)
            destination: Destination path (relative to base_dir)
            
        Returns:
            True if move was successful
            
        Raises:
            FileNotFoundError: If source doesn't exist
            IsADirectoryError: If source is a directory
            ValueError: If destination extension not allowed
        """
        # Validate the paths
        source_path = self._validate_path(source)
        dest_path = self._validate_path(destination)
        
        # Check if source exists
        if not os.path.exists(source_path):
            logger.warning(f"Source file not found: {source}")
            raise FileNotFoundError(f"Source file not found: {source}")
        
        # Validate the source is not a directory
        if os.path.isdir(source_path):
            logger.warning(f"Source is a directory: {source}")
            raise IsADirectoryError(f"Source is a directory: {source}")
        
        # Validate destination extension
        self._validate_extension(destination)
        
        # Ensure the destination directory exists
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        
        # Move the file
        logger.debug(f"Moving file from {source} to {destination}")
        os.rename(source_path, dest_path)
        
        return True
    
    async def apply_diff_to_file(self, path: str, diff_content: str) -> Dict[str, Any]:
        """Apply a unified diff to a file safely.
        
        Args:
            path: Path to the file (relative to base_dir)
            diff_content: Unified diff content to apply
            
        Returns:
            Dictionary with success status, lines applied, and any errors
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If diff cannot be applied or extension not allowed
        """
        # Validate the path
        full_path = self._validate_path(path)
        
        # Check if file exists
        if not os.path.exists(full_path):
            logger.warning(f"File not found: {path}")
            raise FileNotFoundError(f"File not found: {path}")
        
        # Validate the file is not a directory
        if os.path.isdir(full_path):
            logger.warning(f"Path is a directory: {path}")
            raise IsADirectoryError(f"Path is a directory: {path}")
        
        # Validate extension
        self._validate_extension(path)
        
        try:
            # Read the original file
            original_content, _ = await self.read_file(path)
            
            # Apply the diff
            logger.debug(f"Applying diff to file: {path}")
            new_content, lines_applied = apply_unified_diff(original_content, diff_content)
            
            # Check if the new content size is within limits
            content_size = len(new_content.encode('utf-8'))
            if content_size > self.max_file_size_mb * 1024 * 1024:
                logger.warning(f"Diff would result in content too large: {content_size} bytes")
                raise ValueError(f"Diff would result in content too large: {content_size} bytes (maximum {self.max_file_size_mb} MB)")
            
            # Write the modified content
            await self.write_file(path, new_content)
            
            logger.info(f"Applied diff to {path}: {lines_applied} lines changed")
            return {
                "success": True,
                "path": path,
                "lines_applied": lines_applied,
                "new_size": content_size,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Error applying diff to {path}: {str(e)}")
            return {
                "success": False,
                "path": path,
                "lines_applied": 0,
                "new_size": 0,
                "error": str(e)
            }
    
    async def generate_file_diff(
        self, 
        path: str, 
        new_content: str, 
        diff_format: DiffFormat = DiffFormat.UNIFIED,
        context_lines: int = 3
    ) -> Dict[str, Any]:
        """Generate a diff between current file content and new content.
        
        Args:
            path: Path to the file (relative to base_dir)
            new_content: New content to compare against
            diff_format: Format of the diff to generate
            context_lines: Number of context lines for unified/context diffs
            
        Returns:
            Dictionary with diff content, stats, and metadata
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If extension not allowed
        """
        try:
            # Read the original file
            original_content, metadata = await self.read_file(path)
            
            # Generate the diff
            logger.debug(f"Generating diff for file: {path}")
            diff_content, stats = generate_diff(
                original_content,
                new_content,
                diff_format=diff_format,
                context_lines=context_lines,
                from_file=f"a/{path}",
                to_file=f"b/{path}"
            )
            
            # Analyze the diff
            analysis = analyze_diff(diff_content)
            
            return {
                "success": True,
                "path": path,
                "diff_content": diff_content,
                "stats": {
                    "lines_added": stats.lines_added,
                    "lines_removed": stats.lines_removed,
                    "lines_modified": stats.lines_modified,
                    "net_change": stats.net_change,
                    "hunks": stats.hunks
                },
                "analysis": analysis,
                "original_size": metadata.size,
                "new_size": len(new_content.encode('utf-8')),
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Error generating diff for {path}: {str(e)}")
            return {
                "success": False,
                "path": path,
                "diff_content": "",
                "stats": {},
                "analysis": {},
                "original_size": 0,
                "new_size": 0,
                "error": str(e)
            }
    