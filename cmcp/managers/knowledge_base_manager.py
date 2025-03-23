"""Knowledge base manager for CMCP."""

import os
from typing import Dict, List, Any, Optional, Tuple
import logging
from pathlib import Path

from cmcp.kb.document_store import DocumentStore
from cmcp.kb.models import DocumentMetadata


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
    
    async def initialize(self) -> None:
        """Initialize the knowledge base manager.
        
        This should be called before using any other methods.
        """
        if self.document_store is None:
            self.document_store = DocumentStore(self.storage_path)
            self.logger.info(f"Initialized knowledge base at: {self.storage_path}")
    
    def fix_path(self, path: str) -> str:
        """Remove any kb prefix ('kb:', 'kb:/', 'kb://', etc.) from path if present.
        
        Args:
            path: The path to fix
            
        Returns:
            Path with kb prefix removed
        """
        if not path:
            return path
            
        if path.startswith("kb:"):
            # Remove the "kb:" prefix
            clean_path = path[3:]
        else:
            clean_path = path
            
        # Remove any leading slashes to prevent accessing the root filesystem
        while clean_path and clean_path.startswith("/"):
            clean_path = clean_path[1:]
            
        return clean_path
    
    async def write_document(self, content: str, 
                          namespace: Optional[str] = None, 
                          collection: Optional[str] = None, 
                          name: Optional[str] = None, 
                          metadata: Optional[Dict[str, Any]] = None) -> str:
        """Write a document to the knowledge base.
        
        Args:
            content: Document content
            namespace: Document namespace (default: "documents")
            collection: Document collection (default: "general")
            name: Document name (if None, one will be generated)
            metadata: Optional document metadata
            
        Returns:
            Document path (namespace/collection/name)
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
        """
        if self.document_store is None:
            raise RuntimeError("Knowledge base manager not initialized. Call initialize() first.")
        
        # Handle metadata
        metadata = metadata or {}
        
        # Get or generate namespace, collection, and name
        namespace = namespace or metadata.get('namespace', 'documents')
        collection = collection or metadata.get('collection', 'general')
        
        # Generate name if not provided
        if not name:
            title = metadata.get('title')
            name = self.document_store.generate_name(title)
        
        # Construct the document path
        doc_path = f"{namespace}/{collection}/{name}"
        
        # Check if content needs chunking (simple size-based approach)
        if len(content) > self.document_store.DEFAULT_CHUNK_SIZE:
            chunks = self.document_store.chunk_content(content)
            
            # Write each chunk
            chunks_info = []
            for i, chunk in enumerate(chunks):
                self.document_store.write_content(doc_path, chunk, i)
                chunks_info.append({
                    "sequence_num": i,
                    "size": len(chunk)
                })
            
            # Write metadata with chunks info
            self.document_store.write_metadata(namespace, collection, name, metadata, chunks_info)
        else:
            # Write single content file
            self.document_store.write_content(doc_path, content)
            
            # Write metadata
            self.document_store.write_metadata(namespace, collection, name, metadata)
        
        return doc_path
    
    async def read_document(self, path: str, chunk_num: Optional[int] = None) -> Dict[str, Any]:
        """Read a document from the knowledge base.
        
        Args:
            path: Document path (namespace/collection/name)
            chunk_num: Optional specific chunk number to read
            
        Returns:
            Dictionary with document content, metadata, and optional nextChunkNum
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If the document doesn't exist
        """
        if self.document_store is None:
            raise RuntimeError("Knowledge base manager not initialized. Call initialize() first.")
        
        # Fix path by removing kb:// prefix if present
        path = self.fix_path(path)
        
        # Read document metadata
        try:
            metadata = self.document_store.read_metadata(path)
        except FileNotFoundError:
            raise FileNotFoundError(f"Document not found: {path}")
        except Exception as e:
            raise e
        
        result = {
            "metadata": metadata.model_dump(),
        }
        
        # Read content based on whether a specific chunk is requested
        if chunk_num is not None:
            # Read specific chunk
            content = self.document_store.read_chunk(path, chunk_num)
            result["content"] = content
            
            # Check if there's a next chunk
            if self.document_store.has_next_chunk(path, chunk_num):
                result["nextChunkNum"] = chunk_num + 1
        else:
            # Read main content
            content = self.document_store.read_content(path)
            result["content"] = content
            
            # Check if there are multiple chunks
            if self.document_store.has_multiple_chunks(path):
                result["nextChunkNum"] = 1
        
        return result
    
    async def add_rdf(self, path: str, triples: List[Tuple[str, str, str]]) -> Dict[str, Any]:
        """Add RDF triples to a document.
        
        Args:
            path: Document path (namespace/collection/name)
            triples: List of RDF triples to add
            
        Returns:
            Dictionary with status and updated triple count
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If the document doesn't exist
        """
        if self.document_store is None:
            raise RuntimeError("Knowledge base manager not initialized. Call initialize() first.")
        
        # Fix path by removing kb:// prefix if present
        path = self.fix_path(path)
        
        # Read document metadata
        try:
            metadata = self.document_store.read_metadata(path)
        except FileNotFoundError:
            raise FileNotFoundError(f"Document not found: {path}")
        
        # Get existing triples
        existing_triples = metadata.rdf_triples
        
        # Add new triples (avoid duplicates)
        updated_triples = list(existing_triples)
        for triple in triples:
            if triple not in updated_triples:
                updated_triples.append(triple)
        
        # Update the metadata
        updated_metadata = self.document_store.update_metadata(
            path, {"rdf_triples": updated_triples}
        )
        
        return {
            "status": "updated",
            "triple_count": len(updated_metadata.rdf_triples)
        }
    
    async def remove_rdf(self, path: str, triples: Optional[List[Tuple[str, str, str]]] = None) -> Dict[str, Any]:
        """Remove RDF triples from a document.
        
        Args:
            path: Document path (namespace/collection/name)
            triples: Specific triples to remove (if None, removes all triples)
            
        Returns:
            Dictionary with status and remaining triple count
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If the document doesn't exist
        """
        if self.document_store is None:
            raise RuntimeError("Knowledge base manager not initialized. Call initialize() first.")
        
        # Fix path by removing kb:// prefix if present
        path = self.fix_path(path)
        
        # Read document metadata
        try:
            metadata = self.document_store.read_metadata(path)
        except FileNotFoundError:
            raise FileNotFoundError(f"Document not found: {path}")
        
        if triples is None:
            # Remove all triples
            updated_triples = []
        else:
            # Remove specific triples
            updated_triples = [t for t in metadata.rdf_triples if t not in triples]
        
        # Update the metadata
        updated_metadata = self.document_store.update_metadata(
            path, {"rdf_triples": updated_triples}
        )
        
        return {
            "status": "updated",
            "triple_count": len(updated_metadata.rdf_triples)
        }
    
    async def add_preference(self, path: str, triples: List[Tuple[str, str, str]]) -> Dict[str, Any]:
        """Add preference triples to a document.
        
        Args:
            path: Document path (namespace/collection/name)
            triples: List of RDF triples to add as preferences
            
        Returns:
            Dictionary with status and updated preference count
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If the document doesn't exist
        """
        if self.document_store is None:
            raise RuntimeError("Knowledge base manager not initialized. Call initialize() first.")
        
        # Fix path by removing kb:// prefix if present
        path = self.fix_path(path)
        
        # Read document metadata
        try:
            metadata = self.document_store.read_metadata(path)
        except FileNotFoundError:
            raise FileNotFoundError(f"Document not found: {path}")
        
        # Get existing preferences
        existing_preferences = metadata.preferences
        
        # Add new preferences (avoid duplicates)
        updated_preferences = list(existing_preferences)
        for triple in triples:
            if triple not in updated_preferences:
                updated_preferences.append(triple)
        
        # Update the metadata
        updated_metadata = self.document_store.update_metadata(
            path, {"preferences": updated_preferences}
        )
        
        return {
            "status": "updated",
            "preference_count": len(updated_metadata.preferences)
        }
    
    async def remove_preference(self, path: str, triples: Optional[List[Tuple[str, str, str]]] = None) -> Dict[str, Any]:
        """Remove preference triples from a document.
        
        Args:
            path: Document path (namespace/collection/name)
            triples: Specific triples to remove (if None, removes all preferences)
            
        Returns:
            Dictionary with status and remaining preference count
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If the document doesn't exist
        """
        if self.document_store is None:
            raise RuntimeError("Knowledge base manager not initialized. Call initialize() first.")
        
        # Fix path by removing kb:// prefix if present
        path = self.fix_path(path)
        
        # Read document metadata
        try:
            metadata = self.document_store.read_metadata(path)
        except FileNotFoundError:
            raise FileNotFoundError(f"Document not found: {path}")
        
        if triples is None:
            # Remove all preferences
            updated_preferences = []
        else:
            # Remove specific preferences
            updated_preferences = [t for t in metadata.preferences if t not in triples]
        
        # Update the metadata
        updated_metadata = self.document_store.update_metadata(
            path, {"preferences": updated_preferences}
        )
        
        return {
            "status": "updated",
            "preference_count": len(updated_metadata.preferences)
        }
    
    async def add_reference(self, path: str, ref_namespace: str = None, ref_collection: str = None, 
                          ref_name: str = None, relation: str = None, ref_path: str = None) -> Dict[str, Any]:
        """Add a reference to another document.
        
        Args:
            path: Document path (namespace/collection/name)
            ref_namespace: Referenced document namespace (if not using ref_path)
            ref_collection: Referenced document collection (if not using ref_path)
            ref_name: Referenced document name (if not using ref_path)
            relation: Relation predicate
            ref_path: Referenced document path (namespace/collection/name), alternative to namespace/collection/name
            
        Returns:
            Dictionary with status and updated reference count
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If source or referenced document doesn't exist
            ValueError: If neither ref_path nor ref_namespace/collection/name are provided
        """
        if self.document_store is None:
            raise RuntimeError("Knowledge base manager not initialized. Call initialize() first.")
        
        # Fix paths by removing kb:// prefix if present
        path = self.fix_path(path)
        
        # Build the reference path from either ref_path or components
        if ref_path:
            resolved_ref_path = self.fix_path(ref_path)
        elif ref_namespace and ref_collection and ref_name:
            resolved_ref_path = f"{ref_namespace}/{ref_collection}/{ref_name}"
        else:
            raise ValueError("Either ref_path or ref_namespace/collection/name must be provided")
        
        # Ensure relation is provided
        if not relation:
            raise ValueError("Relation predicate must be provided")
        
        # Read document metadata for source document
        try:
            metadata = self.document_store.read_metadata(path)
        except FileNotFoundError:
            raise FileNotFoundError(f"Source document not found: {path}")
        
        # Check if referenced document exists
        try:
            self.document_store.read_metadata(resolved_ref_path)
        except FileNotFoundError:
            raise FileNotFoundError(f"Referenced document not found: {resolved_ref_path}")
        
        # Create the reference triple
        reference = (f"kb://{path}", relation, f"kb://{resolved_ref_path}")
        
        # Get existing references
        existing_references = metadata.references
        
        # Add new reference if not already present
        updated_references = list(existing_references)
        if reference not in updated_references:
            updated_references.append(reference)
        
        # Update the metadata
        updated_metadata = self.document_store.update_metadata(
            path, {"references": updated_references}
        )
        
        return {
            "status": "updated",
            "reference_count": len(updated_metadata.references)
        }
    
    async def remove_reference(self, path: str, ref_namespace: Optional[str] = None, 
                             ref_collection: Optional[str] = None, ref_name: Optional[str] = None,
                             relation: Optional[str] = None, ref_path: Optional[str] = None) -> Dict[str, Any]:
        """Remove references from a document, optionally filtering by attributes.
        
        Args:
            path: Document path (namespace/collection/name)
            ref_namespace: Optional referenced document namespace filter
            ref_collection: Optional referenced document collection filter
            ref_name: Optional referenced document name filter
            relation: Optional relation predicate filter
            ref_path: Optional complete reference path to filter by
            
        Returns:
            Dictionary with status and remaining reference count
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If document doesn't exist
        """
        if self.document_store is None:
            raise RuntimeError("Knowledge base manager not initialized. Call initialize() first.")
        
        # Fix path by removing kb:// prefix if present
        path = self.fix_path(path)
        if ref_path:
            ref_path = self.fix_path(ref_path)
        
        # Read document metadata
        try:
            metadata = self.document_store.read_metadata(path)
        except FileNotFoundError:
            raise FileNotFoundError(f"Document not found: {path}")
        
        # Get existing references
        references = metadata.references
        
        if not any([ref_namespace, ref_collection, ref_name, relation, ref_path]):
            # No filters provided, remove all references
            updated_references = []
        else:
            # Filter references to remove
            updated_references = []
            for ref in references:
                should_keep = True
                subject, pred, obj = ref
                
                # If relation filter is provided and matches, mark for removal
                if relation and pred == relation:
                    should_keep = False
                
                # If ref_path is provided, check for exact match
                if ref_path and obj == f"kb://{ref_path}":
                    should_keep = False
                # Otherwise, check component filters
                elif ref_namespace or ref_collection or ref_name:
                    ref_path_from_obj = obj.replace("kb://", "")
                    ref_parts = ref_path_from_obj.split("/")
                    if len(ref_parts) >= 3:
                        if (ref_namespace and ref_parts[0] == ref_namespace) or \
                           (ref_collection and ref_parts[1] == ref_collection) or \
                           (ref_name and ref_parts[2] == ref_name):
                            should_keep = False
                
                if should_keep:
                    updated_references.append(ref)
        
        # Update the metadata
        updated_metadata = self.document_store.update_metadata(
            path, {"references": updated_references}
        )
        
        return {
            "status": "updated",
            "reference_count": len(updated_metadata.references)
        }
    
    async def list_documents(self, 
                           namespace: Optional[str] = None, 
                           collection: Optional[str] = None,
                           recursive: bool = True) -> List[str]:
        """List documents in the knowledge base.
        
        Args:
            namespace: Optional namespace to filter by
            collection: Optional collection to filter by (requires namespace)
            recursive: Whether to list recursively
            
        Returns:
            List of document paths
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
        """
        if self.document_store is None:
            raise RuntimeError("Knowledge base manager not initialized. Call initialize() first.")
        
        # Handle special case where path is just 'kb:'
        if namespace == '' or namespace is True:
            namespace = None
        
        # List documents using the document store
        if recursive:
            return self.document_store.find_documents_recursive(namespace, collection)
        else:
            return self.document_store.find_documents_shallow(namespace, collection)
    
    async def move_document(self, 
                          current_path: str, 
                          new_namespace: Optional[str] = None, 
                          new_collection: Optional[str] = None, 
                          new_name: Optional[str] = None) -> str:
        """Move a document to a new location.
        
        Args:
            current_path: Current document path
            new_namespace: New namespace (if None, keeps current)
            new_collection: New collection (if None, keeps current)
            new_name: New name (if None, keeps current)
            
        Returns:
            New document path
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If the document doesn't exist
        """
        if self.document_store is None:
            raise RuntimeError("Knowledge base manager not initialized. Call initialize() first.")
        
        # Fix path
        current_path = self.fix_path(current_path)
        
        # Read document data
        try:
            metadata = self.document_store.read_metadata(current_path)
            content = self.document_store.read_content(current_path)
        except FileNotFoundError:
            raise FileNotFoundError(f"Document not found: {current_path}")
        
        # Get new path components, defaulting to current ones if not specified
        new_namespace = new_namespace or metadata.namespace
        new_collection = new_collection or metadata.collection
        new_name = new_name or metadata.name
        
        # Write document to new location
        new_path = await self.write_document(
            content=content,
            namespace=new_namespace,
            collection=new_collection,
            name=new_name,
            metadata=metadata.metadata
        )
        
        # TODO: Optionally delete the old document
        
        self.logger.info(f"Moved document: {current_path} → {new_path}")
        
        return new_path