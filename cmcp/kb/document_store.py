"""Document store for the knowledge base."""

import os
import json
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional, Iterator
from pathlib import Path

from .models import DocumentMetadata, DocumentChunk


class DocumentStore:
    """Handles storage and retrieval of documents in the knowledge base."""
    
    DEFAULT_CHUNK_SIZE = 4096  # 4KB chunks by default
    
    def __init__(self, base_path: str):
        """Initialize the document store with a base path.
        
        Args:
            base_path: Base path for document storage
        """
        self.base_path = Path(base_path).resolve()
        os.makedirs(self.base_path, exist_ok=True)
    
    def validate_path(self, path: str) -> str:
        """Validate and normalize a document path.
        
        Args:
            path: Document path to validate (namespace/collection/name)
            
        Returns:
            Normalized path
            
        Raises:
            ValueError: If path is invalid
        """
        # Remove leading/trailing slashes and normalize
        normalized = path.strip().strip('/')
        
        if not normalized:
            raise ValueError(f"Path cannot be empty")
        
        # Ensure the path follows the namespace/collection/name format
        parts = normalized.split('/')
        if len(parts) != 3:
            raise ValueError(f"Invalid path format: {path}. Path must be in the form 'namespace/collection/name'")
        
        # Validate each part
        for part in parts:
            if not part or not re.match(r'^[\w\-]+$', part):
                raise ValueError(f"Invalid path component: {part}. Components must be alphanumeric with hyphens.")
        
        return normalized
    
    def generate_name(self, title: Optional[str] = None) -> str:
        """Generate a name for a document.
        
        Args:
            title: Optional title to base the name on
            
        Returns:
            Generated name
        """
        if title:
            # Create a slug from the title
            name = self._slugify(title)
        else:
            # Create a timestamp-based name
            timestamp = int(time.time())
            name = f"doc-{timestamp}"
        
        return name
    
    def _slugify(self, text: str) -> str:
        """Convert text to a URL-friendly slug.
        
        Args:
            text: Text to convert
            
        Returns:
            URL-friendly slug
        """
        # Convert to lowercase
        slug = text.lower()
        
        # Replace spaces with hyphens
        slug = slug.replace(' ', '-')
        
        # Remove special characters
        slug = re.sub(r'[^a-z0-9\-]', '', slug)
        
        # Remove consecutive hyphens
        slug = re.sub(r'\-+', '-', slug)
        
        # Trim hyphens from start and end
        slug = slug.strip('-')
        
        # Limit length
        if len(slug) > 64:
            slug = slug[:64]
        
        # Ensure we have something
        if not slug:
            timestamp = int(time.time())
            slug = f"doc-{timestamp}"
        
        return slug
    
    def ensure_directory(self, path: str) -> Path:
        """Ensure the directory for a document exists.
        
        Args:
            path: Document path (namespace/collection/name)
            
        Returns:
            Path to the document directory
        """
        document_path = self.base_path / path
        os.makedirs(document_path, exist_ok=True)
        return document_path
    
    def write_content(self, path: str, content: str, chunk_num: Optional[int] = None) -> Path:
        """Write content to a document file.
        
        Args:
            path: Document path (namespace/collection/name)
            content: Content to write
            chunk_num: Optional chunk number for chunked documents
            
        Returns:
            Path to the written file
        """
        document_path = self.ensure_directory(path)
        
        if chunk_num is not None:
            filename = f"content.{chunk_num:04d}.txt"
        else:
            filename = "content.txt"
        
        file_path = document_path / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return file_path
    
    def read_content(self, path: str) -> str:
        """Read content from a document.
        
        Args:
            path: Document path (namespace/collection/name)
            
        Returns:
            Document content
            
        Raises:
            FileNotFoundError: If document doesn't exist
        """
        document_path = self.base_path / path
        
        # First try to read content.txt
        content_path = document_path / "content.txt"
        if content_path.exists():
            with open(content_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        # If not found, try content.0000.txt (first chunk)
        chunk_path = document_path / "content.0000.txt"
        if chunk_path.exists():
            with open(chunk_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        raise FileNotFoundError(f"Document content not found for path: {path}")
    
    def read_chunk(self, path: str, chunk_num: int) -> str:
        """Read a specific chunk from a document.
        
        Args:
            path: Document path (namespace/collection/name)
            chunk_num: Chunk number to read
            
        Returns:
            Chunk content
            
        Raises:
            FileNotFoundError: If chunk doesn't exist
        """
        document_path = self.base_path / path
        chunk_path = document_path / f"content.{chunk_num:04d}.txt"
        
        if not chunk_path.exists():
            raise FileNotFoundError(f"Chunk {chunk_num} not found for document {path}")
        
        with open(chunk_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def has_next_chunk(self, path: str, chunk_num: int) -> bool:
        """Check if a document has a next chunk after the given one.
        
        Args:
            path: Document path (namespace/collection/name)
            chunk_num: Current chunk number
            
        Returns:
            True if next chunk exists, False otherwise
        """
        document_path = self.base_path / path
        next_chunk_path = document_path / f"content.{chunk_num+1:04d}.txt"
        return next_chunk_path.exists()
    
    def has_multiple_chunks(self, path: str) -> bool:
        """Check if a document has multiple chunks.
        
        Args:
            path: Document path (namespace/collection/name)
            
        Returns:
            True if document has multiple chunks, False otherwise
        """
        document_path = self.base_path / path
        
        # Check if any content.NNNN.txt files exist where NNNN > 0000
        for file_path in document_path.glob("content.*.txt"):
            match = re.search(r'content\.(\d{4})\.txt', file_path.name)
            if match and int(match.group(1)) > 0:
                return True
        
        return False
    
    def chunk_content(self, content: str, max_chunk_size: Optional[int] = None) -> List[str]:
        """Split content into chunks.
        
        Args:
            content: Content to split
            max_chunk_size: Maximum chunk size in characters
            
        Returns:
            List of content chunks
        """
        if max_chunk_size is None:
            max_chunk_size = self.DEFAULT_CHUNK_SIZE
        
        # Simple character-based chunking
        chunks = []
        for i in range(0, len(content), max_chunk_size):
            chunks.append(content[i:i + max_chunk_size])
        
        return chunks
    
    def write_metadata(self, namespace: str, collection: str, name: str, 
                     metadata: Dict[str, Any], chunks_info: Optional[List[Dict[str, Any]]] = None) -> Path:
        """Write document metadata file.
        
        Args:
            namespace: Document namespace
            collection: Document collection
            name: Document name
            metadata: Document metadata
            chunks_info: Optional information about chunks
            
        Returns:
            Path to the metadata file
        """
        path = f"{namespace}/{collection}/{name}"
        document_path = self.ensure_directory(path)
        metadata_path = document_path / "metadata.json"
        
        # Create document metadata
        doc_metadata = DocumentMetadata(
            namespace=namespace,
            collection=collection,
            name=name,
            **{k: v for k, v in metadata.items() if k not in ['namespace', 'collection', 'name']}
        )
        
        # Add chunks information if provided
        if chunks_info:
            doc_metadata.chunked = True
            doc_metadata.chunks = [
                DocumentChunk(
                    path=f"{path}/content.{chunk['sequence_num']:04d}.txt",
                    size=chunk['size'],
                    sequence_num=chunk['sequence_num']
                )
                for chunk in chunks_info
            ]
        
        # Write to metadata file
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(doc_metadata.model_dump(), f, indent=2, default=str)
        
        return metadata_path
    
    def read_metadata(self, path: str) -> DocumentMetadata:
        """Read document metadata file.
        
        Args:
            path: Document path (namespace/collection/name)
            
        Returns:
            Document metadata
            
        Raises:
            FileNotFoundError: If metadata file doesn't exist
        """
        document_path = self.base_path / path
        metadata_path = document_path / "metadata.json"
        
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found for document {path}")
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Convert loaded data to DocumentMetadata
        return DocumentMetadata(**data)
    
    def update_metadata(self, path: str, updates: Dict[str, Any]) -> DocumentMetadata:
        """Update document metadata file.
        
        Args:
            path: Document path (namespace/collection/name)
            updates: Dictionary of fields to update
            
        Returns:
            Updated document metadata
            
        Raises:
            FileNotFoundError: If metadata file doesn't exist
        """
        # Read existing metadata
        metadata = self.read_metadata(path)
        
        # Update fields
        metadata_dict = metadata.model_dump()
        metadata_dict.update(updates)
        metadata_dict['updated_at'] = datetime.utcnow()
        
        # Don't allow changing path components through updates
        metadata_dict['namespace'] = metadata.namespace
        metadata_dict['collection'] = metadata.collection
        metadata_dict['name'] = metadata.name
        
        # Write back
        document_path = self.base_path / path
        metadata_path = document_path / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata_dict, f, indent=2, default=str)
        
        return DocumentMetadata(**metadata_dict)
    
    def find_documents_recursive(self, namespace: Optional[str] = None, collection: Optional[str] = None) -> List[str]:
        """Find all documents recursively under a namespace/collection.
        
        Args:
            namespace: Optional namespace to filter by
            collection: Optional collection to filter by (requires namespace)
            
        Returns:
            List of document paths
        """
        search_path = self.base_path
        
        # Build the search path based on provided filters
        if namespace:
            search_path = search_path / namespace
            if collection:
                search_path = search_path / collection
        
        # Search for metadata.json files
        documents = []
        for metadata_file in search_path.glob("**/metadata.json"):
            doc_path = metadata_file.parent
            relative_path = doc_path.relative_to(self.base_path)
            documents.append(str(relative_path).replace('\\', '/'))
        
        return documents
    
    def find_documents_shallow(self, namespace: Optional[str] = None, collection: Optional[str] = None) -> List[str]:
        """Find documents directly under a namespace/collection (non-recursive).
        
        Args:
            namespace: Optional namespace to filter by
            collection: Optional collection to filter by (requires namespace)
            
        Returns:
            List of document paths
        """
        search_path = self.base_path
        
        # Build the search path based on provided filters
        if namespace:
            search_path = search_path / namespace
            if collection:
                search_path = search_path / collection
        
        # Define the glob pattern based on filters
        if namespace and collection:
            # Looking for documents in a specific collection
            pattern = "*"
        elif namespace:
            # Looking for collections in a namespace
            pattern = "*/*"
        else:
            # Looking for namespaces
            pattern = "*/*/*"
        
        # Search for metadata.json files
        documents = []
        for metadata_file in search_path.glob(f"{pattern}/metadata.json"):
            doc_path = metadata_file.parent
            relative_path = doc_path.relative_to(self.base_path)
            documents.append(str(relative_path).replace('\\', '/'))
        
        return documents