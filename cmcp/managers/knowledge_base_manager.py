# cmcp/managers/knowledge_base_manager.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Knowledge base manager for CMCP."""

import os
import re
from typing import Dict, List, Any, Optional, Tuple, NamedTuple
from datetime import datetime
import logging
from pathlib import Path

from cmcp.kb.document_store import DocumentStore
from cmcp.kb.models import DocumentIndex, ImplicitRDFTriple, DocumentFragment
from cmcp.kb.path import PathComponents, PartialPathComponents


class KnowledgeBaseManager:
    """Manages the knowledge base, providing high-level operations on documents."""
    
    def __init__(self, storage_path: Optional[str] = None):
        """Initialize the knowledge base manager.
        
        Args:
            storage_path: Path to the storage location
        """
        self.storage_path = storage_path or os.environ.get("CMCP_KB_STORAGE_PATH", "./kb_storage")
        self.document_store = None
        self.logger = logging.getLogger(__name__)
    
    @classmethod
    def from_env(cls) -> 'KnowledgeBaseManager':
        """Create a KnowledgeBaseManager instance using environment variables.
        
        Returns:
            KnowledgeBaseManager instance
        """
        storage_path = os.environ.get("CMCP_KB_STORAGE_PATH")
        return cls(storage_path)
    
    def check_initialized(self) -> None:
        """Check if the knowledge base manager is initialized.
        
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
        """
        if self.document_store is None:
            raise RuntimeError("Knowledge base manager not initialized. Call initialize() first.")
    
    async def initialize(self) -> None:
        """Initialize the knowledge base manager.
        
        This should be called before using any other methods.
        """
        if self.document_store is None:
            self.document_store = DocumentStore(self.storage_path)
            self.logger.info(f"Initialized knowledge base at: {self.storage_path}")
    
    async def write_content(self, components: PathComponents, content: str) -> DocumentIndex:
        """Write content to a document in the knowledge base.
        
        Args:
            components: PathComponents with namespace, collection, and name
            content: Document content
            
        Returns:
            Updated document index
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
        """
        self.check_initialized()
            
        # Check if content needs chunking (simple size-based approach)
        if len(content) > self.document_store.DEFAULT_FRAGMENT_SIZE:

            if components.fragment:
                raise ValueError(f"Cannot chunk content for {components.urn} because it is a fragment")

            chunks = self.document_store.chunk_content(content)
            
            # Write each chunk
            fragments : Dict[str, DocumentFragment] = {}
            for i, chunk in enumerate(chunks):
                fragment_component = components.copy()
                fragment_component.fragment = f"{i:04d}"    
                filename = self.document_store.write_content(fragment_component, chunk)
                fragments[filename] = DocumentFragment(
                    sequence_num=i,
                    size=len(chunk)
                )
            
            # Update metadata with chunks info
            try:
                # Try to read existing metadata
                existing_index = self.document_store.read_index(components)
                # Update with chunks info
                self.document_store.update_index(components, {"chunked": True, "fragments": fragments})
            except FileNotFoundError:
                # Index doesn't exist yet, this needs to error
                raise ValueError(f"Document index not found: {components.urn}")

        else:
            # Write single content file
            self.document_store.write_content(components, content)
        
        existing_index = self.document_store.read_index(components)
        
        return existing_index
    
    async def update_metadata(self,
                           components: PathComponents,
                           metadata: Dict[str, Any]) -> DocumentIndex:
        """Update metadata for a document in the knowledge base.
        
        Args:
            components: PathComponents with namespace, collection, and name
            metadata: Document metadata to update

        Returns:
            Updated document index
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If the document doesn't exist
        """
        self.check_initialized()
        
        # Check if document exists
        try:
            current_index = self.document_store.read_index(components)
        except FileNotFoundError:
            raise FileNotFoundError(f"Document not found: {components.urn}")
        
        # Update metadata
        current_index.metadata.update(metadata)
        
        # Update index
        self.document_store.update_index(components, {"metadata": current_index.metadata})
        
        return current_index
    
    async def read_content(self, components: PathComponents) -> Optional[str]:
        """Read content from a document in the knowledge base.
        
        Args:
            components: PathComponents with namespace, collection, name and optional fragment

        Returns:
            Document content or None if the content doesn't exist
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If the document metadata doesn't exist
        """
        self.check_initialized()
        
        # First check if index exists
        try:
            current_index = self.document_store.read_index(components)
        except FileNotFoundError:
            raise FileNotFoundError(f"Document not found: {components.urn}")
        
        # Try to read content
        try:
            content = self.document_store.read_content(components)
            return content
        except FileNotFoundError:
            # Content doesn't exist, but index does
            return None
    
    async def add_preference(self, components: PathComponents, preferences: List[ImplicitRDFTriple]) -> Dict[str, Any]:
        """Add preference triples to a document.
        
        Args:
            components: PathComponents with namespace, collection, and name
            preferences: List of RDF predicate-object pairs to add as preferences
            
        Returns:
            Dictionary with status and updated preference count
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If the document doesn't exist
        """
        self.check_initialized()
        
        # Read document metadata
        try:
            index = self.document_store.read_index(components)
        except FileNotFoundError:
            raise FileNotFoundError(f"Document not found: {components.urn}")
        
        # Get existing preferences
        updated_preferences = list(index.preferences)
        
        for preference in preferences:
            if preference not in updated_preferences:
                updated_preferences.append(preference)
        
        # Update the metadata
        updated_index = self.document_store.update_index(
            components, {"preferences": updated_preferences}
        )
        
        return {
            "status": "updated",
            "preference_count": len(updated_index.preferences)
        }
    
    async def remove_preference(self, components: PathComponents, preferences: List[ImplicitRDFTriple]) -> Dict[str, Any]:
        """Remove preference triples from a document.
        
        Args:
            components: PathComponents with namespace, collection, and name
            preferences: Specific triples to remove (if None, removes all preferences)
            
        Returns:
            Dictionary with status and remaining preference count
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If the document doesn't exist
        """
        self.check_initialized()
        
        # Read document metadata
        try:
            index = self.document_store.read_index(components)
        except FileNotFoundError:
            raise FileNotFoundError(f"Document not found: {components.urn}")
        
        # Current preferences
        current_preferences = index.preferences
        
        # Filter out the preferences to remove
        updated_preferences = [p for p in current_preferences if p not in preferences]
        
        # Update the index
        updated_index = self.document_store.update_index(
            components, {"preferences": updated_preferences}
        )
        
        return {
            "status": "updated",
            "preference_count": len(updated_index.preferences)
        }
    
    async def remove_all_preferences(self, components: PathComponents) -> Dict[str, Any]:
        """Remove all preference triples from a document.
        
        Args:
            components: PathComponents with namespace, collection, and name
            
        Returns:
            Dictionary with status and remaining preference count
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If the document doesn't exist
        """
        return await self.remove_preference(components, None)
    
    async def add_reference(self, 
                          components: PathComponents,
                          ref_components: PathComponents,
                          relation: str) -> Dict[str, Any]:
        """Add a reference to another document.
        
        Args:
            components: PathComponents with namespace, collection, and name
            ref_components: PathComponents with namespace, collection, and name
            relation: Relation predicate
            
        Returns:
            Dictionary with status and updated reference count
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If source or referenced document doesn't exist
        """
        self.check_initialized()
        
        # Read document metadata for source document
        try:
            index = self.document_store.read_index(components)
        except FileNotFoundError:
            raise FileNotFoundError(f"Source document not found: {components.urn}")
        
        # Check if referenced document exists
        try:
            self.document_store.read_index(ref_components)
        except FileNotFoundError:
            raise FileNotFoundError(f"Referenced document not found: {ref_components.urn}")
        
        # Create the reference as ImplicitRDFTriple
        # The predicate is the relation, the object is the referenced document URN
        reference = ImplicitRDFTriple(predicate=relation, object=ref_components.urn)
        
        # Get existing references
        existing_references = index.references
        
        # Add new reference if not already present
        updated_references = list(existing_references)
        if reference not in updated_references:
            updated_references.append(reference)
        
        # Update the metadata
        updated_index = self.document_store.update_index(
            components, {"references": updated_references}
        )
        
        return {
            "status": "updated",
            "reference_count": len(updated_index.references)
        }
    
    async def remove_reference(self, 
                            components: PathComponents,
                            ref_components: PathComponents,
                            relation: str) -> Dict[str, Any]:
        """Remove references from a document matching the specified attributes.
        
        Args:
            components: PathComponents with namespace, collection, and name
            ref_components: PathComponents with namespace, collection, and name
            relation: Relation predicate
            
        Returns:
            Dictionary with status and remaining reference count
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If document doesn't exist
        """
        self.check_initialized()
        
        # Read document metadata
        try:
            index = self.document_store.read_index(components)
        except FileNotFoundError:
            raise FileNotFoundError(f"Document not found: {components.urn}")
        
        # Get existing references
        references = index.references
        
        # Create the reference as ImplicitRDFTriple to remove
        target_ref = ImplicitRDFTriple(predicate=relation, object=ref_components.urn)
        
        # Filter references to remove the specified one
        updated_references = [ref for ref in references if ref != target_ref]
        
        # Update the metadata
        updated_index = self.document_store.update_index(
            components, {"references": updated_references}
        )
        
        return {
            "status": "updated",
            "reference_count": len(updated_index.references)
        }
    
    async def list_documents(self, 
                           components: Optional[PartialPathComponents] = None,
                           recursive: bool = True) -> List[str]:
        """List documents in the knowledge base.
        
        Args:
            components: Optional PartialPathComponents to filter by
            recursive: Whether to list recursively
            
        Returns:
            List of document paths
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
        """
        self.check_initialized()
        
        if components is None:
            components = PartialPathComponents()
        
        # List documents using the document store
        if recursive:
            return self.document_store.find_documents_recursive(components)
        else:
            return self.document_store.find_documents_shallow(components)
    
    async def move_document(self, 
                          components: PathComponents,
                          new_components: PathComponents) -> DocumentIndex:
        """Move a document to a new location.
        
        Args:
            components: Current document components
            new_components: New document components
            
        Returns:
            New document index
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If the document doesn't exist
        """
        self.check_initialized()
        
        # Read document data
        try:
            index = self.document_store.read_index(components)
            #self.document_store.validate_index(new_components)
        except FileNotFoundError:
            raise FileNotFoundError(f"Document not found: {components.urn}")

        # We need to move the folder from the old path to the new path, and then rewrite the index
        self.document_store.move_document(components, new_components)
        
        self.logger.info(f"Moved document: {components.path} → {new_components.path}")
        
        return index
        
    async def delete_document(self,
                           components: PathComponents) -> Dict[str, Any]:
        """Delete a document from the knowledge base.
        
        Args:
            components: PathComponents with namespace, collection, and name
            
        Returns:
            Dictionary with status and deleted path
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If the document doesn't exist
        """
        self.check_initialized()
        
        # Check if document exists
        try:
            self.document_store.read_index(components)
        except FileNotFoundError:
            raise FileNotFoundError(f"Document not found: {components.urn}")
        
        # Delete document files
        self.document_store.delete_document(components)
        
        self.logger.info(f"Deleted document: {components.path}")
        
        return {
            "status": "deleted",
            "path": components.path,
            "urn": components.urn
        }
    
    async def create_document(self,
                          components: PathComponents,
                          metadata: Optional[Dict[str, Any]] = None) -> DocumentIndex:
        """Create a new document with metadata but no content.
        
        This is part of a two-step process for document creation:
        1. Create document with metadata
        2. Write content separately
        
        This approach prevents wasting tokens if document creation fails.
        
        Args:
            components: PathComponents with namespace, collection, and name
            metadata: Optional document metadata
            
        Returns:
            Document path (namespace/collection/name)
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            ValueError: If content already exists at the path
        """
        self.check_initialized()
        
        # Check if content already exists
        document_path_obj = self.document_store.base_path / components.path
        content_path = document_path_obj / "content.txt"
        chunk_path = document_path_obj / "content.0000.txt"
        
        if content_path.exists() or chunk_path.exists():
            raise ValueError(f"Content already exists at path: {components.path}")
        
        # Initialize empty metadata
        metadata_dict = metadata or {}

        # Create index
        index = DocumentIndex(
            namespace=components.namespace,
            collection=components.collection,
            name=components.name,
            type="document",
            subtype="text",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            content_type="text/plain",
            chunked=False,
            fragments={},
            preferences=[],
            references=[],
            indices=[],
            metadata=metadata_dict
        )
        
        # Create directory structure and write metadata
        self.document_store.write_index(components, index)
        
        return index
    
    async def read_document(self, components: PathComponents) -> DocumentIndex:
        """Read a document from the knowledge base.
        
        Args:
            components: PathComponents with namespace, collection, and name
            
        Returns:
            DocumentIndex
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If the document doesn't exist
        """
        self.check_initialized()
        
        try:
            # Read document metadata
            index = self.document_store.read_index(components)
        except FileNotFoundError:
            raise FileNotFoundError(f"Document not found: {components.urn}")
        except Exception as e:
            raise e
        
        return index