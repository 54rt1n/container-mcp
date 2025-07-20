# cmcp/kb/document_store.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Document store for the knowledge base."""

import os
import json
import re
import time
import shutil
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

from .models import DocumentIndex, DocumentFragment
from .path import PathComponents, PartialPathComponents

logger = logging.getLogger(__name__)


class DocumentStore:
    """Handles storage and retrieval of documents in the knowledge base."""
    
    DEFAULT_FRAGMENT_SIZE = 4096  # 4KB chunks by default
    
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
    
    def ensure_directory(self, components: PathComponents) -> Path:
        """Ensure the directory for a document exists.
        
        Args:
            components: PathComponents with namespace, collection, and name
            
        Returns:
            Path to the document directory
        """
        document_path = self.base_path / components.path
        os.makedirs(document_path, exist_ok=True)
        return document_path
    
    def write_content(self, components: PathComponents, content: str) -> str:
        """Write content to a document file.
        
        Args:
            components: PathComponents with namespace, collection, name and optional fragment
            content: Content to write
            
        Returns:
            Path to the written file
        """
        document_path = self.ensure_directory(components)
        
        filename = components.get_fragment_name(prefix="content", default="0000", ext="txt")
        
        file_path = document_path / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return filename
    
    def read_content(self, components: PathComponents) -> str:
        """Read content from a document.
        
        Args:
            components: PathComponents with namespace, collection, and name
                        Can include an optional fragment to specify a file
            
        Returns:
            Document content
            
        Raises:
            FileNotFoundError: If document doesn't exist
        """
        document_path = self.base_path / components.path

        # If fragment is specified, try to read that specific file
        if components.fragment:
            # Use the same naming convention as write_content
            fragment_filename = components.get_fragment_name(prefix="content", default="0000", ext="txt")
            fragment_path = document_path / fragment_filename
            if fragment_path.exists():
                with open(fragment_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                raise FileNotFoundError(f"Fragment file {fragment_filename} not found for document {components.path}")
        
        # No fragment or fragment file not found, try standard content files
        content_path = document_path / "content.txt"
        if content_path.exists():
            with open(content_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        # If not found, try content.0000.txt (first fragment)
        chunk_path = document_path / "content.0000.txt"
        if chunk_path.exists():
            with open(chunk_path, 'r', encoding='utf-8') as f:
                return f.read()

        # If not found, we will have to read the index and get the fragment with the lowest sequence number
        index = self.read_index(components)
        if index.fragments:
            for fragment, fragment_info in sorted(index.fragments.items(), key=lambda x: int(x[1].sequence_num)):
                chunk_path = document_path / f"content.{fragment}.txt"
                if chunk_path.exists():
                    with open(chunk_path, 'r', encoding='utf-8') as f:
                        return f.read()

        raise FileNotFoundError(f"Document content not found for path: {components.path}")

    def check_content(self, components: PathComponents) -> bool:
        """Check if content exists for a document.
        
        Args:
            components: PathComponents with namespace, collection, and name
        """
        document_path = self.base_path / components.path
        filename = components.get_fragment_name(prefix="content", default="0000", ext="txt")
        return (document_path / filename).exists()
    
    def chunk_content(self, content: str, max_fragment_size: Optional[int] = None) -> List[str]:
        """Split content into fragments.
        
        Args:
            content: Content to split
            max_fragment_size: Maximum fragment size in characters
            
        Returns:
            List of content chunks
        """
        if max_fragment_size is None:
            max_fragment_size = self.DEFAULT_FRAGMENT_SIZE
        
        # Simple character-based chunking
        fragments = []
        for i in range(0, len(content), max_fragment_size):
            fragments.append(content[i:i + max_fragment_size])
        
        return fragments
    
    def write_index(self, components: PathComponents, index: DocumentIndex) -> Path:
        """Write document index file.
        
        Args:
            components: PathComponents with namespace, collection, and name
            index: Document index
            
        Returns:
            Path to the index file
        """
        document_path = self.ensure_directory(components)
        index_path = document_path / "index.json"

        index_dict = index.model_dump()
        
        # Create document index using components
        doc_index = DocumentIndex(
            namespace=components.namespace,
            collection=components.collection,
            name=components.name,
            **{k: v for k, v in index_dict.items() if k not in ['namespace', 'collection', 'name', 'fragments', 'created_at']}
        )
        
        # Add fragments information if provided
        if index.fragments:
            doc_index.chunked = True
            doc_index.fragments = index.fragments
        
        # Write to index file
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(doc_index.model_dump_json(indent=2))
        
        return index_path
    
    def check_index(self, components: PathComponents) -> bool:
        """Check if document index file exists.
        
        Args:
            components: PathComponents with namespace, collection, and name
        """
        document_path = self.base_path / components.path
        index_path = document_path / "index.json"
        return index_path.exists()
    
    def read_index(self, components: PathComponents) -> DocumentIndex:
        """Read document index file.
        
        Args:
            components: PathComponents with namespace, collection, and name
            
        Returns:
            Document metadata
            
        Raises:
            FileNotFoundError: If metadata file doesn't exist
        """
        document_path = self.base_path / components.path
        index_path = document_path / "index.json"
        
        if not index_path.exists():
            raise FileNotFoundError(f"Index file not found for document {components.uri}")
        
        with open(index_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Convert loaded data to DocumentIndex
        return DocumentIndex(**data)
    
    def update_index(self, components: PathComponents, updates: Dict[str, Any]) -> DocumentIndex:
        """Update document index file.
        
        Args:
            components: PathComponents with namespace, collection, and name
            updates: Dictionary of fields to update
            
        Returns:
            Updated document index
            
        Raises:
            FileNotFoundError: If index file doesn't exist
        """
        # Read existing index
        index = self.read_index(components)
        
        # Update fields
        index_dict = index.model_dump()
        index_dict.update(updates)
        new_index = DocumentIndex(**index_dict)
        new_index.updated_at = datetime.now(timezone.utc)
        
        # Don't allow changing path components through updates
        new_index.namespace = index.namespace
        new_index.collection = index.collection
        new_index.name = index.name

        # Write back
        document_path = self.base_path / components.path
        index_path = document_path / "index.json"
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(new_index.model_dump_json(indent=2))
        
        return new_index
    
    def find_documents_recursive(self, components: PartialPathComponents) -> List[str]:
        """Find all documents recursively under a namespace/collection.
        
        Args:
            components: PartialPathComponents with namespace, collection, and name
            
        Returns:
            List of document paths
        """
        search_path = self.base_path
        
        # Build the search path based on provided filters
        if components.namespace:
            search_path = search_path / components.namespace
            if components.collection:
                search_path = search_path / components.collection
                if components.name:
                    search_path = search_path / components.name
        
        # Search for index.json files
        documents = []
        logger.info(f"Searching for documents in: {search_path}")
        for index_file in search_path.glob("**/index.json"):
            doc_path = index_file.parent
            relative_path = doc_path.relative_to(self.base_path)
            documents.append(str(relative_path).replace('\\', '/'))
        
        return documents
    
    def find_documents_shallow(self, components: PartialPathComponents) -> List[str]:
        """Find documents in the knowledge base (non-recursive).
        
        Args:
            components: PartialPathComponents with namespace, collection, and name
            
        Returns:
            List of document paths in format namespace/collection/name
        """
        if components.namespace is None:
            # List all namespaces (shallow mode)
            return [d.name for d in self.base_path.iterdir() if d.is_dir()]
        
        namespace_path = self.base_path / components.namespace
        if not namespace_path.exists():
            return []
            
        if components.collection is None:
            # List collections in the namespace
            return [f"{components.namespace}/{d.name}" for d in namespace_path.iterdir() if d.is_dir()]
        
        collection_path = namespace_path / components.collection
        if not collection_path.exists():
            return []

        if components.name is None:
            # List documents in the collection
            return [f"{components.namespace}/{components.collection}/{d.name}" for d in collection_path.iterdir() if d.is_dir()]
        else:
            # List documents in the collection/name
            document_path = collection_path / components.name
            if not document_path.exists():
                return []
            return [f"{components.namespace}/{components.collection}/{components.name}"]
    
    def delete_document(self, components: PathComponents) -> None:
        """Delete a document from the knowledge base.
        
        Args:
            components: PathComponents with namespace, collection, and name
            
        Raises:
            FileNotFoundError: If document doesn't exist
        """
        document_path = self.base_path / components.path
        
        if not document_path.exists():
            raise FileNotFoundError(f"Document not found: {components.uri}")
        
        # Delete all files in the document directory
        for file_path in document_path.glob("*"):
            file_path.unlink()
        
        # Remove the directory
        document_path.rmdir()
        
        # Check if parent directories are empty and remove them if they are
        collection_path = document_path.parent
        namespace_path = collection_path.parent
        
        # Try to remove collection directory if empty
        try:
            if collection_path.exists() and not any(collection_path.iterdir()):
                collection_path.rmdir()
                
                # Try to remove namespace directory if empty
                if namespace_path.exists() and not any(namespace_path.iterdir()):
                    namespace_path.rmdir()
        except OSError:
            # If we can't remove the directories, that's ok
            pass

        return None
    
    def move_document(self, components: PathComponents, new_components: PathComponents) -> None:
        """Move a document to a new location.
        
        Args:
            components: PathComponents with namespace, collection, and name
            new_components: PathComponents with namespace, collection, and name
        """
        document_path = self.base_path / components.path
        new_document_path = self.base_path / new_components.path

        if not document_path.exists():
            raise FileNotFoundError(f"Document not found: {components.uri}")
        
        if new_document_path.exists():
            raise FileNotFoundError(f"New document path already exists: {new_components.uri}")
        
        # Move the document directory
        shutil.move(document_path, new_document_path)

        # Update the index
        index = self.read_index(new_components)
        index.namespace = new_components.namespace
        index.collection = new_components.collection
        index.name = new_components.name
        self.write_index(new_components, index)
        
        return None

    def validate_index(self, components: PathComponents) -> None:
        """Validate the index of a document.
        
        Args:
            components: PathComponents with namespace, collection, and name
        """
        document_path = self.base_path / components.path
        if not document_path.exists():
            raise FileNotFoundError(f"Document not found: {components.path}")
        
        index_path = document_path / "index.json"
        if not index_path.exists():
            raise FileNotFoundError(f"Index file not found: {components.path}")
        
        # Check if our namespace, collection, and name are correct
        index = self.read_index(components)
        if index.namespace != components.namespace:
            raise ValueError(f"Namespace mismatch: {index.namespace} != {components.namespace}")
        if index.collection != components.collection:
            raise ValueError(f"Collection mismatch: {index.collection} != {components.collection}")
        if index.name != components.name:
            raise ValueError(f"Name mismatch: {index.name} != {components.name}")
        
        # Check if the fragments exist
        for fragment in index.fragments.keys():
            fragment_path = document_path / f"content.{fragment}.txt"
            if not fragment_path.exists():
                raise FileNotFoundError(f"Fragment file not found: {fragment_path}")
        
        return None