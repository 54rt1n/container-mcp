import os
import aiofiles
import logging
from cmcp.types.file import FileMetadata, FileEntry

logger = logging.getLogger(__name__)

async def read_file(path: str, max_file_size_mb: int = 100, encoding: str = "utf-8") -> tuple[str, FileMetadata]:
    """Read a file and return its content and metadata."""
    try:
        # Check file size
        file_size = os.path.getsize(path)
        if file_size > max_file_size_mb * 1024 * 1024:
            logger.warning(f"File too large: {file_size} bytes")
            raise ValueError(f"File too large: {file_size} bytes (maximum {max_file_size_mb} MB)")
        
        # Create metadata
        metadata = FileMetadata(
            size=file_size,
            modified_time=os.path.getmtime(path),
            is_directory=False
        )
        
        # Read the file
        logger.debug(f"Reading file: {path}")
        async with aiofiles.open(path, 'r', encoding=encoding) as f:
            content = await f.read()
        
        return content, metadata
    
    except Exception as e:
        logger.error(f"Error reading file {path}: {str(e)}")
        raise
        
        
async def write_file(path: str, content: str, encoding: str = "utf-8") -> bool:
    """Write content to a file."""
    try:
        async with aiofiles.open(path, 'w', encoding=encoding) as f:
            await f.write(content)
        return True
    except Exception as e:
        logger.error(f"Error writing file {path}: {str(e)}")
        raise

async def list_directory(path: str, recursive: bool = False) -> list[FileEntry]:
    """List directory contents."""
    try:
        entries = []
        for entry in os.listdir(path):
            if recursive and os.path.isdir(os.path.join(path, entry)):
                entries.extend(await list_directory(os.path.join(path, entry), recursive))
            else:
                entries.append(FileEntry(
                    name=entry,
                    metadata=FileMetadata(
                        size=os.path.getsize(os.path.join(path, entry)),
                        modified_time=os.path.getmtime(os.path.join(path, entry)),
                        is_directory=os.path.isdir(os.path.join(path, entry))
                    )
                ))
        return entries
    except Exception as e:
        logger.error(f"Error listing directory {path}: {str(e)}")
        raise

async def delete_file(path: str) -> bool:
    """Delete a file."""
    try:
        os.remove(path)
        return True
    except Exception as e:
        logger.error(f"Error deleting file {path}: {str(e)}")
        raise