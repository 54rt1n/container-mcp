# cmcp/managers/file_manager.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""File Manager for secure file operations."""

import os
import aiofiles
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional

from cmcp.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FileMetadata:
    """Metadata about a file."""
    
    size: int
    modified_time: float
    is_directory: bool


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
    
    async def read_file(self, path: str) -> Tuple[str, FileMetadata]:
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
        
        # Check file size
        file_size = os.path.getsize(full_path)
        if file_size > self.max_file_size_mb * 1024 * 1024:
            logger.warning(f"File too large: {file_size} bytes")
            raise ValueError(f"File too large: {file_size} bytes (maximum {self.max_file_size_mb} MB)")
        
        # Create metadata
        metadata = FileMetadata(
            size=file_size,
            modified_time=os.path.getmtime(full_path),
            is_directory=False
        )
        
        # Read the file
        logger.debug(f"Reading file: {path}")
        async with aiofiles.open(full_path, 'r') as f:
            content = await f.read()
        
        return content, metadata
    
    async def write_file(self, path: str, content: str) -> bool:
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
        async with aiofiles.open(full_path, 'w') as f:
            await f.write(content)
        
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
        
        if recursive:
            # Walk the directory tree recursively
            for root, dirs, files in os.walk(full_path):
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