# cmcp/types/file.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0
from dataclasses import dataclass

@dataclass
class FileMetadata:
    """Metadata about a file."""
    
    size: int
    modified_time: float
    is_directory: bool


# file entry
@dataclass
class FileEntry:
    """File entry."""

    name: str
    metadata: FileMetadata