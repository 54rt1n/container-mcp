# cmcp/managers/knowledge_base_manager.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Knowledge base manager for CMCP."""

import os
import re
import asyncio
from typing import Dict, List, Any, Optional, Tuple, NamedTuple, Set
from datetime import datetime, timezone
import logging
from pathlib import Path

from cmcp.kb.document_store import DocumentStore
from cmcp.kb.models import DocumentIndex, ImplicitRDFTriple, DocumentFragment
from cmcp.kb.path import PathComponents, PartialPathComponents
from cmcp.utils.logging import get_logger
from cmcp.config import AppConfig

logger = get_logger(__name__)


class KnowledgeBaseManager:
    """Manages the knowledge base, providing high-level operations on documents."""
    
    def __init__(self, 
                 storage_path: str,
                 timeout_default: int,
                 timeout_max: int,
                 search_enabled: bool = True,
                 sparse_index_path: Optional[str] = None,
                 graph_index_path: Optional[str] = None,
                 reranker_model: Optional[str] = None,
                 search_relation_predicates: Optional[List[str]] = None,
                 search_graph_neighbor_limit: int = 1000):
        """Initialize the knowledge base manager.
        
        Args:
            storage_path: Path to the storage location
            timeout_default: Default timeout in seconds
            timeout_max: Maximum allowed timeout in seconds
            search_enabled: Whether search functionality is enabled
            sparse_index_path: Path to sparse search index directory
            graph_index_path: Path to graph search index directory
            reranker_model: Name of the reranker model to use
            search_relation_predicates: Predicates to follow during graph expansion
            search_graph_neighbor_limit: Max number of neighbors to retrieve in graph search
        """
        self.storage_path = storage_path
        self.timeout_default = timeout_default
        self.timeout_max = timeout_max
        self.document_store = None
        self.logger = logger
        
        # Search configuration
        self.search_enabled = search_enabled
        self.sparse_index_path = sparse_index_path or os.path.join(storage_path, "search/sparse_idx")
        self.graph_index_path = graph_index_path or os.path.join(storage_path, "search/graph_idx")
        self.reranker_model = reranker_model or "mixedbread-ai/mxbai-rerank-base-v1"
        self.search_relation_predicates = search_relation_predicates or ["references"]
        self.search_graph_neighbor_limit = search_graph_neighbor_limit
        
        # Search components (initialized in initialize())
        self.sparse_search_index = None
        self.graph_search_index = None
        self.reranker = None
        
        # Locks for concurrent access to search indices
        self.sparse_index_lock = asyncio.Lock()
        self.graph_index_lock = asyncio.Lock()
        
        logger.debug(f"KnowledgeBaseManager initialized with storage path at {self.storage_path}")
        if self.search_enabled:
            logger.debug(f"Search enabled with sparse index at {self.sparse_index_path}, "
                        f"graph index at {self.graph_index_path}, "
                        f"reranker model {self.reranker_model}")
    
    @classmethod
    def from_env(cls, config: Optional[AppConfig] = None) -> 'KnowledgeBaseManager':
        """Create a KnowledgeBaseManager instance using configuration.
        
        Args:
            config: Optional configuration object, loads from environment if not provided
            
        Returns:
            KnowledgeBaseManager instance
        """
        if config is None:
            from cmcp.config import load_config
            config = load_config()
        
        logger.debug(f"Creating KnowledgeBaseManager from environment configuration: {config.kb_config}")
        
        return cls(
            storage_path=config.kb_config.storage_path,
            timeout_default=config.kb_config.timeout_default,
            timeout_max=config.kb_config.timeout_max,
            search_enabled=config.kb_config.search_enabled,
            sparse_index_path=config.kb_config.sparse_index_path,
            graph_index_path=config.kb_config.graph_index_path,
            reranker_model=config.kb_config.reranker_model,
            search_relation_predicates=config.kb_config.search_relation_predicates,
            search_graph_neighbor_limit=config.kb_config.search_graph_neighbor_limit
        )
    
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
            # Ensure storage directory exists
            os.makedirs(self.storage_path, exist_ok=True)
            
            self.document_store = DocumentStore(self.storage_path)
            self.logger.info(f"Initialized knowledge base at: {self.storage_path}")
            
            # Initialize search components
            if self.search_enabled:
                try:
                    from cmcp.kb.search import SparseSearchIndex, GraphSearchIndex, Reranker
                    
                    self.logger.info(f"Initializing search components...")
                    # Create necessary directories
                    os.makedirs(self.sparse_index_path, exist_ok=True)
                    os.makedirs(self.graph_index_path, exist_ok=True)
                    
                    # Initialize components
                    self.sparse_search_index = SparseSearchIndex(self.sparse_index_path)
                    self.graph_search_index = GraphSearchIndex(self.graph_index_path)
                    self.reranker = Reranker(self.reranker_model)
                    
                    self.logger.info(f"Search indices initialized at {self.sparse_index_path} and {self.graph_index_path}")
                    self.logger.info(f"Reranker initialized with model {self.reranker_model}")
                except ImportError as e:
                    self.logger.error(f"Failed to import search dependencies: {e}. Search disabled.")
                    self.search_enabled = False
                except Exception as e:
                    self.logger.error(f"Failed to initialize search components: {e}", exc_info=True)
                    self.search_enabled = False
    
    async def write_content(self, components: PathComponents, content: str) -> DocumentIndex:
        """Write content to a document in the knowledge base.
        
        Also updates the sparse search index if search is enabled.

        Args:
            components: PathComponents with namespace, collection, and name
            content: Document content

        Returns:
            Updated document index

        Raises:
            RuntimeError: If the knowledge base manager is not initialized
        """
        self.check_initialized()
        
        # Update the document content
        content_path = self.document_store.write_content(components, content)
        
        # Update document index with additional metadata (just the timestamp, not content_path)
        index_update = {
            "updated_at": datetime.now(timezone.utc),
        }
        
        # Update search indexes if enabled
        if self.search_enabled:
            if self.sparse_search_index:
                try:
                    self.logger.debug(f"Updating sparse search index for: {components.urn}")
                    
                    # Use lock to ensure only one update happens at a time
                    async with self.sparse_index_lock:
                        # Run blocking Tantivy operations in a separate thread
                        await asyncio.to_thread(
                            self._update_sparse_index_sync,
                            components.urn,
                            content
                        )
                        
                    self.logger.debug(f"Updated sparse search index for: {components.urn}")
                except Exception as e:
                    self.logger.error(f"Failed to update sparse search index: {e}", exc_info=True)
                    # Continue with the non-search operations
        
        # Update the index with the new metadata
        updated_index = self.document_store.update_index(components, index_update)
        
        return updated_index
    
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

    async def check_index(self, components: PathComponents) -> bool:
        """Check if index exists for a document in the knowledge base.
        
        Args:
            components: PathComponents with namespace, collection, name
        """
        self.check_initialized()
        return self.document_store.check_index(components)

    async def check_content(self, components: PathComponents) -> bool:
        """Check if content exists for a document in the knowledge base.
        
        Args:
            components: PathComponents with namespace, collection, name and optional fragment
            
        """
        self.check_initialized()
        
        # Check if index exists
        return self.document_store.check_content(components)
    
    async def read_content(self, components: PathComponents) -> Optional[str]:
        """Read content of a document.
        
        Args:
            components: PathComponents for the document
            
        Returns:
            Document content or None if not found
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If the document doesn't exist
        """
        self.check_initialized()
        
        try:
            # Read document index to get content path
            index = self.document_store.read_index(components)
            
            try:
                # Read the actual content file
                return self.document_store.read_content(components)
            except FileNotFoundError:
                # Content file not found, but index exists
                self.logger.warning(f"Content file not found for document: {components.urn}")
                return None
        except FileNotFoundError:
            # If we can't find the document index, it doesn't exist at all
            raise FileNotFoundError(f"Document not found: {components.urn}")
        except Exception as e:
            # Other errors like missing content file
            self.logger.exception(f"Error reading content for {components.urn}: {e}")
            return None  # Return None for content but don't fail
    
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
        self.check_initialized()
        
        # Read document metadata
        try:
            index = self.document_store.read_index(components)
        except FileNotFoundError:
            raise FileNotFoundError(f"Document not found: {components.urn}")
        
        # Update the index with empty preferences
        updated_index = self.document_store.update_index(
            components, {"preferences": []}
        )
        
        return {
            "status": "updated",
            "preference_count": len(updated_index.preferences)
        }
    
    async def add_reference(self, 
                          components: PathComponents,
                          ref_components: PathComponents,
                          relation: str) -> Dict[str, Any]:
        """Add a reference to another document.
        
        Args:
            components: PathComponents of the source document
            ref_components: PathComponents of the referenced document
            relation: Relation type (e.g., 'references', 'seeAlso')
            
        Returns:
            Dictionary with status information
        
        Raises:
            RuntimeError: If not initialized
            FileNotFoundError: If either document doesn't exist
        """
        self.check_initialized()
        
        # Check if both documents exist
        try:
            source_index = self.document_store.read_index(components)
        except FileNotFoundError:
            raise FileNotFoundError(f"Source document not found: {components.urn}")
        
        try:
            ref_index = self.document_store.read_index(ref_components)
        except FileNotFoundError:
            raise FileNotFoundError(f"Referenced document not found: {ref_components.urn}")
        
        # Add the reference relation to the source document
        triple = ImplicitRDFTriple(
            predicate=relation,
            object=ref_components.urn
        )
        
        # Get existing references and check if reference already exists
        existing_references = list(source_index.references)
        ref_exists = triple in existing_references
        
        if not ref_exists:
            # Add to references
            existing_references.append(triple)
            # Update document index
            self.document_store.update_index(components, {"references": existing_references})
            
            # Add reverse reference to the target document's referenced_by field
            reverse_triple = ImplicitRDFTriple(
                predicate=relation,
                object=components.urn
            )
            
            existing_referenced_by = list(ref_index.referenced_by)
            if reverse_triple not in existing_referenced_by:
                existing_referenced_by.append(reverse_triple)
                self.document_store.update_index(ref_components, {"referenced_by": existing_referenced_by})
                self.logger.debug(f"Added reverse reference: {ref_components.urn} referenced_by {components.urn}")
            
            # Update graph search index
            if self.search_enabled and self.graph_search_index:
                try:
                    self.logger.debug(f"Adding reference to graph search index: {components.urn} -> {ref_components.urn}")
                    
                    # Use lock to ensure only one update happens at a time
                    async with self.graph_index_lock:
                        # Run blocking Tantivy operations in a separate thread
                        await asyncio.to_thread(
                            self._add_triple_sync,
                            components.urn,
                            relation,
                            ref_components.urn,
                            "reference"
                        )
                        
                    self.logger.debug(f"Updated graph search index with reference: {components.urn} -> {ref_components.urn}")
                except Exception as e:
                    self.logger.error(f"Failed to update graph search index: {e}", exc_info=True)
                    # Continue with the non-search operations
        
        return {
            "status": "success",
            "message": "Reference added" if not ref_exists else "Reference already exists",
            "added": not ref_exists
        }
    
    async def remove_reference(self, 
                            components: PathComponents,
                            ref_components: PathComponents,
                            relation: str) -> Dict[str, Any]:
        """Remove a reference to another document.
        
        Args:
            components: PathComponents with namespace, collection, and name
            ref_components: PathComponents with namespace, collection, and name
            relation: Relation predicate
            
        Returns:
            Dictionary with status and updated reference count
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If the document doesn't exist
        """
        self.check_initialized()
        
        # Read document metadata for source document
        try:
            index = self.document_store.read_index(components)
        except FileNotFoundError:
            raise FileNotFoundError(f"Source document not found: {components.urn}")
        
        # Create the reference as ImplicitRDFTriple that we want to remove
        reference = ImplicitRDFTriple(predicate=relation, object=ref_components.urn)
        
        # Get existing references
        existing_references = index.references
        
        # Remove reference if found
        updated_references = [ref for ref in existing_references if ref != reference]
        
        # Only update if something changed
        if len(updated_references) != len(existing_references):
            # Update the metadata
            update_data = {"references": updated_references}
            updated_index = self.document_store.update_index(
                components, update_data
            )
            
            # Remove reverse reference from the target document's referenced_by field
            try:
                ref_index = self.document_store.read_index(ref_components)
                reverse_triple = ImplicitRDFTriple(
                    predicate=relation,
                    object=components.urn
                )
                
                existing_referenced_by = ref_index.referenced_by
                updated_referenced_by = [ref for ref in existing_referenced_by if ref != reverse_triple]
                
                if len(updated_referenced_by) != len(existing_referenced_by):
                    self.document_store.update_index(ref_components, {"referenced_by": updated_referenced_by})
                    self.logger.debug(f"Removed reverse reference: {ref_components.urn} no longer referenced_by {components.urn}")
                    
            except FileNotFoundError:
                # Target document no longer exists, which is fine - the reverse reference is already gone
                self.logger.debug(f"Target document {ref_components.urn} not found when removing reverse reference")
            except Exception as e:
                self.logger.warning(f"Failed to remove reverse reference from {ref_components.urn}: {e}")
            
            # Update graph search index
            if self.search_enabled and self.graph_search_index:
                try:
                    self.logger.debug(f"Removing reference from graph search index: {components.urn} -> {ref_components.urn}")
                    
                    # Use lock to ensure only one update happens at a time
                    async with self.graph_index_lock:
                        # Run blocking Tantivy operations in a separate thread
                        await asyncio.to_thread(
                            self._delete_triple_sync,
                            components.urn,
                            relation,
                            ref_components.urn,
                            "reference"
                        )
                        
                    self.logger.debug(f"Removed reference from graph search index: {components.urn} -> {ref_components.urn}")
                except Exception as e:
                    self.logger.error(f"Failed to update graph search index: {e}", exc_info=True)
                    # Continue with the non-search operations
            
            return {
                "status": "updated",
                "reference_count": len(updated_index.references)
            }
        else:
            return {
                "status": "unchanged",
                "reference_count": len(existing_references)
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
        
        # Update all references that point to the old document location
        old_urn = components.urn
        new_urn = new_components.urn
        
        # Find all documents that reference the moved document and update their references
        if index.referenced_by:
            self.logger.info(f"Updating {len(index.referenced_by)} reverse references for moved document")
            
            for reverse_ref in index.referenced_by:
                try:
                    # Parse the URN of the referencing document
                    referencing_components = PathComponents.parse_path(reverse_ref.object)
                    referencing_index = self.document_store.read_index(referencing_components)
                    
                    # Update references in the referencing document
                    updated_references = []
                    references_updated = False
                    
                    for ref in referencing_index.references:
                        if ref.object == old_urn and ref.predicate == reverse_ref.predicate:
                            # Update this reference to point to the new URN
                            updated_ref = ImplicitRDFTriple(predicate=ref.predicate, object=new_urn)
                            updated_references.append(updated_ref)
                            references_updated = True
                            self.logger.debug(f"Updated reference in {referencing_components.urn}: {old_urn} -> {new_urn}")
                        else:
                            updated_references.append(ref)
                    
                    if references_updated:
                        self.document_store.update_index(referencing_components, {"references": updated_references})
                        
                except Exception as e:
                    self.logger.error(f"Failed to update reference in {reverse_ref.object}: {e}")
        
        # Update the moved document's referenced_by to reflect the new URN in reverse references
        try:
            moved_index = self.document_store.read_index(new_components)
            updated_referenced_by = []
            
            for ref_by in moved_index.referenced_by:
                # The referenced_by entries should point to the new URN as the object
                # But we need to update any that still point to the old URN
                if ref_by.object == old_urn:
                    updated_ref_by = ImplicitRDFTriple(predicate=ref_by.predicate, object=new_urn)
                    updated_referenced_by.append(updated_ref_by)
                else:
                    updated_referenced_by.append(ref_by)
            
            if updated_referenced_by != moved_index.referenced_by:
                self.document_store.update_index(new_components, {"referenced_by": updated_referenced_by})
                
        except Exception as e:
            self.logger.error(f"Failed to update referenced_by for moved document: {e}")
        
        # Update search indices with the new URN
        if self.search_enabled:
            # Update sparse search index if document has content
            try:
                content = await self.read_content(new_components)
                if content and self.sparse_search_index:
                    self.logger.debug(f"Updating sparse search index for moved document: {old_urn} -> {new_urn}")
                    
                    async with self.sparse_index_lock:
                        await asyncio.to_thread(
                            self._update_moved_document_sparse_sync,
                            old_urn,
                            new_urn,
                            content
                        )
                    
                    self.logger.debug(f"Updated sparse search index for moved document: {new_urn}")
            except Exception as e:
                self.logger.error(f"Failed to update sparse search index for moved document: {e}", exc_info=True)
            
            # Update graph search index for all triples involving this document
            if self.graph_search_index:
                try:
                    self.logger.debug(f"Updating graph search index for moved document: {old_urn} -> {new_urn}")
                    
                    async with self.graph_index_lock:
                        await asyncio.to_thread(
                            self._update_moved_document_graph_sync,
                            old_urn,
                            new_urn
                        )
                    
                    self.logger.debug(f"Updated graph search index for moved document: {new_urn}")
                except Exception as e:
                    self.logger.error(f"Failed to update graph search index for moved document: {e}", exc_info=True)
        
        self.logger.info(f"Moved document: {components.path} → {new_components.path}")
        
        return index
        
    async def archive_document(self, components: PathComponents) -> Dict[str, Any]:
        """Archive a document by removing it from indices and moving it to archive location.
        
        This removes the document from search indices, cleans up bidirectional references,
        and moves the document to archive/<path> instead of permanently deleting it.
        
        Args:
            components: PathComponents for the document
            
        Returns:
            Operation status with archive location
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
        """
        self.check_initialized()
        
        # Check if document exists before trying to archive it
        try:
            exists = self.document_store.check_index(components)
            if not exists:
                return {
                    "status": "not_found",
                    "message": f"Document not found: {components.urn}"
                }
        except Exception as e:
            self.logger.error(f"Error checking document existence: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error checking document: {str(e)}"
            }
        
        # Read document index for reference cleanup
        try:
            index = self.document_store.read_index(components)
        except Exception as e:
            self.logger.error(f"Error reading document index: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error reading document: {str(e)}"
            }
        
        # Clean up references TO other documents (and their reverse references)
        for ref in index.references:
            try:
                ref_components = PathComponents.parse_path(ref.object)
                ref_index = self.document_store.read_index(ref_components)
                
                # Remove the reverse reference from the target document
                reverse_triple = ImplicitRDFTriple(predicate=ref.predicate, object=components.urn)
                updated_referenced_by = [r for r in ref_index.referenced_by if r != reverse_triple]
                
                if len(updated_referenced_by) != len(ref_index.referenced_by):
                    self.document_store.update_index(ref_components, {"referenced_by": updated_referenced_by})
                    self.logger.debug(f"Removed reverse reference from {ref_components.urn}")
                    
            except Exception as e:
                self.logger.warning(f"Failed to clean up reverse reference for {ref.object}: {e}")
        
        # Clean up references FROM other documents that point to this document
        # Note: We keep the local referenced_by entries in the archived document for reference
        for reverse_ref in index.referenced_by:
            try:
                referencing_components = PathComponents.parse_path(reverse_ref.object)
                referencing_index = self.document_store.read_index(referencing_components)
                
                # Remove the reference from the referencing document
                reference_to_remove = ImplicitRDFTriple(predicate=reverse_ref.predicate, object=components.urn)
                updated_references = [r for r in referencing_index.references if r != reference_to_remove]
                
                if len(updated_references) != len(referencing_index.references):
                    self.document_store.update_index(referencing_components, {"references": updated_references})
                    self.logger.debug(f"Removed reference from {referencing_components.urn}")
                    
            except Exception as e:
                self.logger.warning(f"Failed to clean up reference from {reverse_ref.object}: {e}")
        
        # Remove from search indices if enabled
        if self.search_enabled:
            # Remove from sparse search index
            if self.sparse_search_index:
                try:
                    self.logger.debug(f"Removing document from sparse search index: {components.urn}")
                    
                    async with self.sparse_index_lock:
                        await asyncio.to_thread(
                            self._delete_sparse_index_sync,
                            components.urn
                        )
                        
                    self.logger.debug(f"Removed document from sparse search index: {components.urn}")
                except Exception as e:
                    self.logger.error(f"Failed to update sparse search index: {e}", exc_info=True)
                    # Continue with archiving even if search update fails
            
            # Remove from graph search index
            if self.graph_search_index:
                try:
                    self.logger.debug(f"Removing document from graph search index: {components.urn}")
                    
                    async with self.graph_index_lock:
                        await asyncio.to_thread(
                            self._delete_document_from_graph_sync,
                            components.urn
                        )
                        
                    self.logger.debug(f"Removed document from graph search index: {components.urn}")
                except Exception as e:
                    self.logger.error(f"Failed to update graph search index: {e}", exc_info=True)
                    # Continue with archiving even if search update fails
        
        # Create archive path - prepend "archive/" to the original path
        archive_components = PathComponents(
            namespace="archive",
            collection=components.namespace,
            subcollections=components.subcollections + [components.collection] if components.subcollections else [components.collection],
            name=components.name
        )
        
        # Move the document to archive location
        try:
            self.document_store.move_document(components, archive_components)
            archive_path = archive_components.path
            
            self.logger.info(f"Archived document: {components.path} → {archive_path}")
            
            return {
                "status": "archived",
                "message": f"Document archived: {components.urn}",
                "original_path": components.path,
                "archive_path": archive_path,
                "archive_urn": archive_components.urn
            }
            
        except Exception as e:
            self.logger.error(f"Error archiving document: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error archiving document: {str(e)}"
            }
    
    async def delete_document(self, components: PathComponents) -> Dict[str, Any]:
        """Delete a document from the knowledge base.
        
        Args:
            components: PathComponents for the document
            
        Returns:
            Operation status
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
        """
        self.check_initialized()
        
        # Check if document exists before trying to delete it
        try:
            exists = self.document_store.check_index(components)
            if not exists:
                return {
                    "status": "not_found",
                    "message": f"Document not found: {components.urn}"
                }
        except Exception as e:
            self.logger.error(f"Error checking document existence: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error checking document: {str(e)}"
            }
        
        # Clean up bidirectional references before deleting the document
        try:
            index = self.document_store.read_index(components)
            
            # Remove all references from this document to other documents (and their reverse references)
            for ref in index.references:
                try:
                    ref_components = PathComponents.parse_path(ref.object)
                    ref_index = self.document_store.read_index(ref_components)
                    
                    # Remove the reverse reference from the target document
                    reverse_triple = ImplicitRDFTriple(predicate=ref.predicate, object=components.urn)
                    updated_referenced_by = [r for r in ref_index.referenced_by if r != reverse_triple]
                    
                    if len(updated_referenced_by) != len(ref_index.referenced_by):
                        self.document_store.update_index(ref_components, {"referenced_by": updated_referenced_by})
                        self.logger.debug(f"Removed reverse reference from {ref_components.urn}")
                        
                except Exception as e:
                    self.logger.warning(f"Failed to clean up reverse reference for {ref.object}: {e}")
            
            # Remove references from other documents that point to this document
            for reverse_ref in index.referenced_by:
                try:
                    referencing_components = PathComponents.parse_path(reverse_ref.object)
                    referencing_index = self.document_store.read_index(referencing_components)
                    
                    # Remove the reference from the referencing document
                    reference_to_remove = ImplicitRDFTriple(predicate=reverse_ref.predicate, object=components.urn)
                    updated_references = [r for r in referencing_index.references if r != reference_to_remove]
                    
                    if len(updated_references) != len(referencing_index.references):
                        self.document_store.update_index(referencing_components, {"references": updated_references})
                        self.logger.debug(f"Removed reference from {referencing_components.urn}")
                        
                except Exception as e:
                    self.logger.warning(f"Failed to clean up reference from {reverse_ref.object}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error during reference cleanup: {e}", exc_info=True)
            # Continue with deletion even if cleanup fails
            
        # Update the search indices if enabled
        if self.search_enabled:
            # Remove from sparse search index
            if self.sparse_search_index:
                try:
                    self.logger.debug(f"Removing document from sparse search index: {components.urn}")
                    
                    # Use lock to ensure only one update happens at a time
                    async with self.sparse_index_lock:
                        # Run blocking Tantivy operations in a separate thread
                        await asyncio.to_thread(
                            self._delete_sparse_index_sync,
                            components.urn
                        )
                        
                    self.logger.debug(f"Removed document from sparse search index: {components.urn}")
                except Exception as e:
                    self.logger.error(f"Failed to update sparse search index: {e}", exc_info=True)
                    # Continue with the non-search operations
            
            # Remove from graph search index
            if self.graph_search_index:
                try:
                    self.logger.debug(f"Removing document from graph search index: {components.urn}")
                    
                    # Use lock to ensure only one update happens at a time
                    async with self.graph_index_lock:
                        # Run blocking Tantivy operations in a separate thread
                        await asyncio.to_thread(
                            self._delete_document_from_graph_sync,
                            components.urn
                        )
                        
                    self.logger.debug(f"Removed document from graph search index: {components.urn}")
                except Exception as e:
                    self.logger.error(f"Failed to update graph search index: {e}", exc_info=True)
                    # Continue with the non-search operations
                    
        # Delete the document from the file system
        try:
            self.document_store.delete_document(components)
            return {
                "status": "deleted",
                "message": f"Document deleted: {components.urn}"
            }
        except Exception as e:
            self.logger.error(f"Error deleting document: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error deleting document: {str(e)}"
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
            DocumentIndex object
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            ValueError: If document already exists at the path
        """
        self.check_initialized()
        
        # Check if document already exists (index file exists)
        if self.document_store.check_index(components):
            raise ValueError(f"Document already exists at path: {components.path}")
        
        # Initialize empty metadata
        metadata_dict = metadata or {}

        # Create index
        index = DocumentIndex(
            namespace=components.namespace,
            collection=components.collection,
            name=components.name,
            type="document",
            subtype="text",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
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
        
        # Return the DocumentIndex object, not the path
        return index
    
    async def read_index(self, components: PathComponents) -> DocumentIndex:
        """Read document index.
        
        Args:
            components: PathComponents for the document
            
        Returns:
            DocumentIndex object
            
        Raises:
            RuntimeError: If the knowledge base manager is not initialized
            FileNotFoundError: If the index file doesn't exist
        """
        self.check_initialized()
        
        try:
            # Read the document index
            return self.document_store.read_index(components)
        except FileNotFoundError:
            raise FileNotFoundError(f"Document not found: {components.urn}")
    
    async def search(self,
                     query: Optional[str] = None,
                     graph_seed_urns: Optional[List[str]] = None,
                     graph_expand_hops: int = 0,
                     relation_predicates: Optional[List[str]] = None,
                     top_k_sparse: int = 50,
                     top_k_rerank: int = 10,
                     filter_urns: Optional[List[str]] = None,
                     include_content: bool = False,
                     include_index: bool = False,
                     use_reranker: bool = True,
                     fuzzy_distance: int = 0) -> List[Dict[str, Any]]:
        """Search the knowledge base using text query and/or graph expansion.
        
        Args:
            query: Text query for sparse search and reranking
            graph_seed_urns: List of starting URNs for graph expansion/filtering
            graph_expand_hops: Number of hops to expand graph relationships (default 0)
            relation_predicates: List of predicates to follow for graph expansion
            top_k_sparse: Number of results to return from initial sparse search
            top_k_rerank: Number of results to return after reranking
            filter_urns: List of urns to filter out of the results
            include_content: Whether to include content in the results
            include_index: Whether to include index in the results
            use_reranker: Whether to use semantic reranking
            fuzzy_distance: Threshold for fuzzy matching (0 = exact, 1-2 recommended)
            
        Returns:
            List of document results with scores and content
        
        Raises:
            RuntimeError: If search is disabled or knowledge base manager is not initialized
            ValueError: If neither query nor graph_filter_urns are provided
        """
        self.check_initialized()
        
        if not self.search_enabled:
            raise RuntimeError("Search is disabled.")
            
        if not query and not filter_urns:
            raise ValueError("Search requires either a query or filter_urns.")
            
        # Use configured predicates if not specified
        if relation_predicates is None:
            relation_predicates = self.search_relation_predicates
            
        # Disable reranking if content is not included - can't rerank without content
        if not include_content and use_reranker:
            self.logger.warning("Disabling reranking because include_content=False. Reranking requires content.")
            use_reranker = False
            
        self.logger.debug(f"Search request: query='{query}', graph_seed_urns={graph_seed_urns}, graph_expand_hops={graph_expand_hops}")

        # 1. First, get candidate URNs from sparse search and/or graph expansion
        candidate_urns, sparse_scores = await self._get_candidate_urns(
            query, graph_seed_urns, graph_expand_hops, relation_predicates, top_k_sparse, filter_urns, fuzzy_distance
        )
        
        if not candidate_urns:
            self.logger.debug("No candidate URNs found, returning empty results")
            return []
            
        # 2. Fetch content for candidates
        documents_with_data, error_documents = await self._fetch_content_for_candidates(
            candidate_urns, sparse_scores, include_content, include_index, use_reranker, query
        )
        
        # 3. Rerank or sort results
        final_results = await self._prepare_final_results(
            query, documents_with_data, error_documents, 
            sparse_scores, use_reranker, top_k_sparse, top_k_rerank
        )
        
        return final_results
    
    async def recover_search_indices(self, rebuild_all: bool = False) -> Dict[str, Any]:
        """Recover or rebuild search indices after corruption or deletion.
        
        This method will attempt to recover both sparse and graph search indices.
        If rebuild_all is True, it will also repopulate the indices with all
        existing documents and their relationships.
        
        Args:
            rebuild_all: If True, rebuild indices from scratch and repopulate with all documents
            
        Returns:
            Dictionary with recovery status for each index type
            
        Raises:
            RuntimeError: If search is disabled or knowledge base manager is not initialized
        """
        self.check_initialized()
        
        if not self.search_enabled:
            raise RuntimeError("Search is disabled.")
        
        recovery_status = {
            "sparse_index": {"status": "skipped", "error": None},
            "graph_index": {"status": "skipped", "error": None},
            "documents_processed": 0,
            "triples_processed": 0
        }
        
        self.logger.info("Starting search index recovery...")
        
        # Recover sparse search index
        if self.sparse_search_index:
            try:
                self.logger.info("Recovering sparse search index...")
                async with self.sparse_index_lock:
                    await asyncio.to_thread(self.sparse_search_index._recover_index)
                recovery_status["sparse_index"]["status"] = "recovered"
                self.logger.info("Sparse search index recovered successfully")
            except Exception as e:
                self.logger.error(f"Failed to recover sparse search index: {e}", exc_info=True)
                recovery_status["sparse_index"]["status"] = "error"
                recovery_status["sparse_index"]["error"] = str(e)
        
        # Recover graph search index
        if self.graph_search_index:
            try:
                self.logger.info("Recovering graph search index...")
                async with self.graph_index_lock:
                    await asyncio.to_thread(self.graph_search_index._recover_index)
                recovery_status["graph_index"]["status"] = "recovered"
                self.logger.info("Graph search index recovered successfully")
            except Exception as e:
                self.logger.error(f"Failed to recover graph search index: {e}", exc_info=True)
                recovery_status["graph_index"]["status"] = "error"
                recovery_status["graph_index"]["error"] = str(e)
        
        # If rebuild_all is requested, repopulate indices with existing documents
        if rebuild_all:
            try:
                self.logger.info("Rebuilding indices from existing documents...")
                await self._rebuild_indices_from_documents(recovery_status)
                self.logger.info("Index rebuild completed")
            except Exception as e:
                self.logger.error(f"Failed to rebuild indices from documents: {e}", exc_info=True)
                recovery_status["rebuild_error"] = str(e)
        
        self.logger.info(f"Search index recovery completed: {recovery_status}")
        return recovery_status
    
    async def _rebuild_indices_from_documents(self, recovery_status: Dict[str, Any]) -> None:
        """Rebuild search indices from all existing documents.
        
        Args:
            recovery_status: Status dictionary to update with progress
        """
        # Get all documents
        all_documents = await self.list_documents(recursive=True)
        recovery_status["total_documents"] = len(all_documents)
        
        docs_processed = 0
        triples_processed = 0
        
        for doc_path in all_documents:
            try:
                components = PathComponents.parse_path(doc_path)
                
                # Read document index and content
                try:
                    index = await self.read_index(components)
                    content = await self.read_content(components)
                    
                    # Update sparse index if content exists
                    if content and self.sparse_search_index:
                        try:
                            async with self.sparse_index_lock:
                                await asyncio.to_thread(
                                    self._update_sparse_index_sync,
                                    components.urn,
                                    content
                                )
                        except Exception as e:
                            self.logger.warning(f"Failed to index content for {components.urn}: {e}")
                    
                    # Update graph index with references and preferences
                    if self.graph_search_index:
                        try:
                            async with self.graph_index_lock:
                                # Add references
                                for ref in index.references:
                                    await asyncio.to_thread(
                                        self._add_triple_sync,
                                        components.urn,
                                        ref.predicate,
                                        ref.object,
                                        "reference"
                                    )
                                    triples_processed += 1
                                
                                # Add preferences
                                for pref in index.preferences:
                                    await asyncio.to_thread(
                                        self._add_triple_sync,
                                        components.urn,
                                        pref.predicate,
                                        pref.object,
                                        "preference"
                                    )
                                    triples_processed += 1
                        except Exception as e:
                            self.logger.warning(f"Failed to index triples for {components.urn}: {e}")
                    
                    docs_processed += 1
                    
                    if docs_processed % 100 == 0:
                        self.logger.info(f"Processed {docs_processed}/{len(all_documents)} documents...")
                        
                except FileNotFoundError:
                    self.logger.warning(f"Document or content not found for {doc_path}, skipping")
                    continue
                    
            except Exception as e:
                self.logger.error(f"Error processing document {doc_path}: {e}")
                continue
        
        recovery_status["documents_processed"] = docs_processed
        recovery_status["triples_processed"] = triples_processed
        self.logger.info(f"Rebuild completed: {docs_processed} documents, {triples_processed} triples processed")

    async def _get_candidate_urns(self, 
                                query: Optional[str], 
                                graph_seed_urns: Optional[List[str]], 
                                graph_expand_hops: int,
                                relation_predicates: List[str],
                                top_k_sparse: int,
                                filter_urns: Optional[List[str]],
                                fuzzy_distance: int = 0) -> Tuple[Set[str], Dict[str, float]]:
        """Get candidate URNs from sparse search and graph expansion.
        
        Args:
            query: Search query
            graph_seed_urns: Initial URNs to start with
            graph_expand_hops: Number of hops to expand graph
            relation_predicates: Relations to follow during expansion
            top_k_sparse: Number of sparse search results to include
            filter_urns: URNs to filter out of the results
            fuzzy_distance: Maximum edit distance for fuzzy matching
            
        Returns:
            Tuple of (candidate URNs set, sparse scores dictionary)
        """
        candidate_urns = set(graph_seed_urns or [])
        sparse_scores = {}  # urn -> score
        
        # 1. Sparse search if query provided
        if query:
            try:
                self.logger.debug(f"Performing sparse search for: {query}")
                
                # Run blocking Tantivy operations in a separate thread
                sparse_results = await asyncio.to_thread(
                    self._search_sparse_sync,
                    query,
                    top_k_sparse,
                    fuzzy_distance,
                    filter_urns
                )
                
                for urn, score in sparse_results:
                    sparse_scores[urn] = score
                    # If filtering by initial URNs, only add if it matches
                    if graph_seed_urns is None or urn in graph_seed_urns:
                        candidate_urns.add(urn)
                
                self.logger.debug(f"Sparse search found {len(sparse_results)} results")
            except Exception as e:
                self.logger.error(f"Error during sparse search: {e}", exc_info=True)
                # Continue with any URNs we might have from graph_filter_urns
        
        # 2. Graph expansion if requested
        if graph_expand_hops > 0 and candidate_urns:
            try:
                self.logger.debug(f"Expanding graph from {len(candidate_urns)} URNs with {graph_expand_hops} hops")
                
                current_urns = set(candidate_urns)
                all_expanded_urns = set(candidate_urns)
                
                for hop in range(graph_expand_hops):
                    if not current_urns:
                        break  # Stop if no new URNs to expand
                        
                    self.logger.debug(f"Graph expansion hop {hop+1}: expanding {len(current_urns)} URNs")
                    
                    # Run blocking Tantivy operations in a separate thread
                    neighbors = await asyncio.to_thread(
                        self._find_neighbors_sync,
                        list(current_urns),
                        relation_predicates,
                        self.search_graph_neighbor_limit,
                        filter_urns
                    )
                    
                    # Find genuinely new URNs
                    new_urns = neighbors - all_expanded_urns
                    all_expanded_urns.update(new_urns)
                    current_urns = new_urns  # Expand these new ones next
                    
                    self.logger.debug(f"Hop {hop+1} found {len(new_urns)} new URNs, total: {len(all_expanded_urns)}")
                
                candidate_urns = all_expanded_urns
            except Exception as e:
                self.logger.error(f"Error during graph expansion: {e}", exc_info=True)
                # Continue with what we have
                
        self.logger.debug(f"Final candidate URNs: {len(candidate_urns)}")
        return candidate_urns, sparse_scores
    
    async def _fetch_content_for_candidates(self, 
                                          candidate_urns: Set[str], 
                                          sparse_scores: Dict[str, float],
                                          include_content: bool,
                                          include_index: bool,
                                          use_reranker: bool,
                                          query: Optional[str] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Fetch content and/or index for candidate URNs.
        
        Args:
            candidate_urns: Set of candidate URNs
            sparse_scores: Dictionary of URN -> sparse score
            include_content: Whether to include content in results
            include_index: Whether to include index in results
            use_reranker: Whether reranking will be used (forces content fetching)
            query: Search query (used to determine if reranking is possible)
            
        Returns:
            Tuple of (documents with requested data, error documents)
        """
        self.logger.debug(f"Fetching data for {len(candidate_urns)} candidate URNs (content: {include_content}, index: {include_index})")
        
        # Determine if we need to fetch content (either requested or needed for reranking)
        need_content_for_reranking = use_reranker and query and self.reranker
        fetch_content = include_content or need_content_for_reranking
        
        documents_with_data = []
        error_documents = []
        
        # NOTE: This assumes URNs directly map to PathComponents.
        # If the URN format ever changes, this logic will need to be updated.
        for urn in candidate_urns:
            try:
                components = PathComponents.parse_path(urn)
                doc_data = {
                    'urn': urn,
                    'sparse_score': sparse_scores.get(urn)
                }
                
                content_fetched = False
                if fetch_content:
                    try:
                        content = await self.read_content(components)
                        if content:
                            doc_data['content'] = content
                            content_fetched = True
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch content for {urn}: {e}")
                        if need_content_for_reranking:
                            # If content is needed for reranking but failed, treat as error
                            error_documents.append({
                                'urn': urn,
                                'sparse_score': sparse_scores.get(urn),
                                'rerank_score': None,
                                'error': f'Failed to fetch content for reranking: {str(e)}'
                            })
                            continue
                
                # Fetch index information if requested
                if include_index:
                    try:
                        index = await self.read_index(components)
                        doc_data['index'] = index.model_dump()
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch index for {urn}: {e}")
                        doc_data['index_error'] = str(e)
                
                # For reranking, we need documents with content
                if need_content_for_reranking:
                    if content_fetched:
                        documents_with_data.append(doc_data)
                    else:
                        # No content found, add to error documents
                        error_documents.append({
                            'urn': urn,
                            'sparse_score': sparse_scores.get(urn),
                            'rerank_score': None,
                            'error': 'No content found for reranking'
                        })
                else:
                    # Not doing reranking, include all documents regardless of content
                    documents_with_data.append(doc_data)
                    
            except Exception as e:
                self.logger.warning(f"Failed to process {urn}: {e}")
                error_documents.append({
                    'urn': urn,
                    'sparse_score': sparse_scores.get(urn),
                    'rerank_score': None,
                    'error': str(e)
                })
                
        self.logger.debug(f"Data fetched for {len(documents_with_data)} documents " 
                         f"({len(error_documents)} errors/missing content)")
        return documents_with_data, error_documents
    
    async def _prepare_final_results(self,
                                   query: Optional[str],
                                   documents_with_data: List[Dict[str, Any]],
                                   error_documents: List[Dict[str, Any]],
                                   sparse_scores: Dict[str, float],
                                   use_reranker: bool,
                                   top_k_sparse: int,
                                   top_k_rerank: int) -> List[Dict[str, Any]]:
        """Prepare final results by reranking or sorting by sparse score.
        
        Args:
            query: Search query
            documents_with_data: Documents with content for reranking
            error_documents: Documents that had errors or no content
            sparse_scores: Dictionary of URN -> sparse score
            use_reranker: Whether to use reranking
            top_k_sparse: Number of top sparse results to use if not reranking
            top_k_rerank: Number of top reranked results to return
            
        Returns:
            Final list of results
        """
        final_results = list(error_documents)  # Start with error documents
        
        # Rerank if requested and possible
        if use_reranker and query and documents_with_data and self.reranker:
            try:
                self.logger.debug(f"Reranking {len(documents_with_data)} documents")
                
                # Run blocking reranker in a separate thread
                reranked_docs = await asyncio.to_thread(
                    self._rerank_docs_sync,
                    query,
                    documents_with_data
                )
                
                # Add reranked docs to final results, potentially overwriting placeholders
                existing_urns_in_final = {res['urn'] for res in final_results}
                for doc in reranked_docs[:top_k_rerank]:
                    if doc['urn'] in existing_urns_in_final:
                        # Update existing entry
                        for item in final_results:
                            if item['urn'] == doc['urn']:
                                item.update(doc)
                                item.pop('error', None)  # Clear error if content was found
                                break
                    else:
                        final_results.append(doc)
                
                # Sort final list by rerank_score (desc), putting None scores last
                final_results.sort(key=lambda x: x.get('rerank_score') if x.get('rerank_score') is not None else float('-inf'), reverse=True)
                self.logger.debug(f"Reranking complete: returning {min(len(final_results), top_k_rerank)} results")
                return final_results[:top_k_rerank]
                
            except Exception as e:
                self.logger.error(f"Reranking failed: {e}", exc_info=True)
                # Fall back to sparse results
        
        # If we get here, either reranking was not requested, failed, or not possible
        if sparse_scores:
            # Combine docs_with_content (which have sparse scores) with error_documents
            self.logger.debug("Using sparse scores for ranking")
            scored_urns = {doc['urn'] for doc in documents_with_data}
            combined = documents_with_data + [res for res in error_documents if res['urn'] not in scored_urns]
            combined.sort(key=lambda x: x.get('sparse_score') if x.get('sparse_score') is not None else float('-inf'), reverse=True)
            self.logger.debug(f"Returning {min(len(combined), top_k_sparse)} results based on sparse scores")
            return combined[:top_k_sparse]
            
        elif documents_with_data:
            # If we have documents but no sparse scores (graph expansion case)
            self.logger.debug("No sparse scores but have documents with content - returning all documents")
            # Add default score of 1.0 to all documents that don't have a score
            for doc in documents_with_data:
                if 'sparse_score' not in doc:
                    doc['sparse_score'] = 1.0
            # Sort alphabetically by URN for reproducibility
            documents_with_data.sort(key=lambda x: x['urn'])
            return documents_with_data
        
        # If no scores at all and no documents with content, just return documents in alphabetical order by URN
        self.logger.debug("No scores or documents with content available, sorting by URN")
        final_results.sort(key=lambda x: x['urn'])
        return final_results[:top_k_rerank]
    
    # Synchronous helper methods for Tantivy operations
    # These are intended to be run in a separate thread via asyncio.to_thread

    def _update_sparse_index_sync(self, urn: str, content: str) -> None:
        """Synchronous method to update sparse search index.
        
        Args:
            urn: Document URN
            content: Document content
            
        Raises:
            Exception: If index update fails
        """
        writer = None
        try:
            writer = self.sparse_search_index.get_writer()
            
            # Only delete if content is non-empty (update case)
            # For empty content, use _delete_sparse_index_sync instead
            if content:
                # Delete existing document if it exists
                self.sparse_search_index.delete_document(writer, urn)
                # Add document with the new content
                self.sparse_search_index.add_document(writer, urn, content)
            else:
                # Just delete the document for empty content
                self.sparse_search_index.delete_document(writer, urn)
                
            # Only commit when everything succeeds
            writer.commit()
            writer = None  # Prevent double-commit in finally block
        except Exception as e:
            self.logger.error(f"Tantivy sparse index update failed for {urn}: {e}")
            raise
        finally:
            # If writer wasn't committed due to an exception, commit it to release resources
            if writer:
                try:
                    writer.commit()
                    self.logger.warning(f"Committed writer after exception for {urn} to release resources")
                except Exception as e_commit:
                    self.logger.error(f"Failed to commit writer after exception: {e_commit}")

    def _delete_sparse_index_sync(self, urn: str) -> None:
        """Synchronous method to delete document from sparse search index.
        
        Args:
            urn: Document URN to delete
            
        Raises:
            Exception: If index deletion fails
        """
        writer = None
        try:
            writer = self.sparse_search_index.get_writer()
            # Delete the document
            self.sparse_search_index.delete_document(writer, urn)
            # Commit when successful
            writer.commit()
            writer = None  # Prevent double-commit in finally block
        except Exception as e:
            self.logger.error(f"Tantivy sparse index deletion failed for {urn}: {e}")
            raise
        finally:
            # If writer wasn't committed due to an exception, commit it to release resources
            if writer:
                try:
                    writer.commit()
                    self.logger.warning(f"Committed writer after exception for {urn} to release resources")
                except Exception as e_commit:
                    self.logger.error(f"Failed to commit writer after exception: {e_commit}")

    def _add_triple_sync(self, subject: str, predicate: str, object_urn: str, triple_type: str) -> None:
        """Synchronous method to add triple to graph index.
        
        Args:
            subject: Subject URN
            predicate: Predicate
            object_urn: Object URN
            triple_type: Type of triple
            
        Raises:
            Exception: If index update fails
        """
        writer = None
        try:
            writer = self.graph_search_index.get_writer()
            self.graph_search_index.add_triple(
                writer, subject, predicate, object_urn, triple_type
            )
            # Commit when successful
            writer.commit()
            writer = None  # Prevent double-commit in finally block
        except Exception as e:
            self.logger.error(f"Tantivy graph triple add failed: {e}")
            raise
        finally:
            # If writer wasn't committed due to an exception, commit it to release resources
            if writer:
                try:
                    writer.commit()
                    self.logger.warning(f"Committed writer after exception for triple {subject}-{predicate}-{object_urn} to release resources")
                except Exception as e_commit:
                    self.logger.error(f"Failed to commit writer after exception: {e_commit}")

    def _delete_triple_sync(self, subject: str, predicate: str, object_urn: str, triple_type: str) -> None:
        """Synchronous method to delete triple from graph index.
        
        Args:
            subject: Subject URN
            predicate: Predicate
            object_urn: Object URN
            triple_type: Type of triple
            
        Raises:
            Exception: If index update fails
        """
        writer = None
        try:
            writer = self.graph_search_index.get_writer()
            self.graph_search_index.delete_triple(
                writer, subject, predicate, object_urn, triple_type
            )
            # Commit when successful
            writer.commit()
            writer = None  # Prevent double-commit in finally block
        except Exception as e:
            self.logger.error(f"Tantivy graph triple delete failed: {e}")
            raise
        finally:
            # If writer wasn't committed due to an exception, commit it to release resources
            if writer:
                try:
                    writer.commit()
                    self.logger.warning(f"Committed writer after exception for triple {subject}-{predicate}-{object_urn} to release resources")
                except Exception as e_commit:
                    self.logger.error(f"Failed to commit writer after exception: {e_commit}")

    def _delete_document_from_graph_sync(self, urn: str) -> None:
        """Synchronous method to remove a document from graph index.
        
        This removes all triples where the document is either subject or object.
        
        Args:
            urn: Document URN
            
        Raises:
            Exception: If index update fails
        """
        import tantivy
        writer = None
        try:
            writer = self.graph_search_index.get_writer()
            # Create a query to match all triples where this document is either subject or object
            subject_term = tantivy.Term.from_field_text("subject", urn)
            object_term = tantivy.Term.from_field_text("object", urn)
            
            query = tantivy.Query.boolean()
            query.add_should(tantivy.Query.term(subject_term))
            query.add_should(tantivy.Query.term(object_term))
            
            writer.delete_query(query)
            # Commit when successful
            writer.commit()
            writer = None  # Prevent double-commit in finally block
        except Exception as e:
            self.logger.error(f"Tantivy graph document removal failed: {e}")
            raise
        finally:
            # If writer wasn't committed due to an exception, commit it to release resources
            if writer:
                try:
                    writer.commit()
                    self.logger.warning(f"Committed writer after exception for {urn} to release resources")
                except Exception as e_commit:
                    self.logger.error(f"Failed to commit writer after exception: {e_commit}")

    def _search_sparse_sync(self, query: str, top_k: int, fuzzy_distance: int = 0, filter_urns: Optional[List[str]] = None) -> List[Tuple[str, float]]:
        """Synchronous method for sparse search.
        
        Args:
            query: Search query
            top_k: Maximum number of results to return
            fuzzy_distance: Maximum edit distance for fuzzy matching (0 = exact, 1-2 recommended)
            filter_urns: List of URNs to exclude from results
            
        Returns:
            List of (urn, score) tuples
            
        Raises:
            Exception: If search fails
        """
        return self.sparse_search_index.search(query, top_k, fuzzy_distance, filter_urns)
        
    def _find_neighbors_sync(self, urns: List[str], relation_predicates: List[str], limit: int, filter_urns: Optional[List[str]] = None) -> Set[str]:
        """Synchronous method for graph expansion.
        
        Args:
            urns: List of URNs to expand
            relation_predicates: List of predicates to follow
            limit: Maximum number of neighbors to return
            filter_urns: List of URNs to exclude from neighbor results
            
        Returns:
            Set of neighbor URNs
            
        Raises:
            Exception: If neighbor search fails
        """
        return self.graph_search_index.find_neighbors(urns, relation_predicates, limit, filter_urns)
    
    def _rerank_docs_sync(self, query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Synchronous method for reranking.
        
        Args:
            query: Search query
            documents: List of documents to rerank
            
        Returns:
            Reranked documents
            
        Raises:
            Exception: If reranking fails
        """
        return self.reranker.rerank(query, documents)
    
    def _update_moved_document_sparse_sync(self, old_urn: str, new_urn: str, content: str) -> None:
        """Synchronous method to update sparse index when document is moved.
        
        Args:
            old_urn: Old document URN
            new_urn: New document URN  
            content: Document content
            
        Raises:
            Exception: If index update fails
        """
        writer = None
        try:
            writer = self.sparse_search_index.get_writer()
            
            # Remove old URN entry
            self.sparse_search_index.delete_document(writer, old_urn)
            
            # Add new URN entry with same content
            self.sparse_search_index.add_document(writer, new_urn, content)
            
            # Commit changes
            writer.commit()
            writer = None  # Prevent double-commit in finally block
        except Exception as e:
            self.logger.error(f"Tantivy sparse index move update failed: {old_urn} -> {new_urn}: {e}")
            raise
        finally:
            if writer:
                try:
                    writer.commit()
                    self.logger.warning(f"Committed writer after exception for move {old_urn} -> {new_urn}")
                except Exception as e_commit:
                    self.logger.error(f"Failed to commit writer after exception: {e_commit}")
    
    def _update_moved_document_graph_sync(self, old_urn: str, new_urn: str) -> None:
        """Synchronous method to update graph index when document is moved.
        
        Updates all triples where the document appears as subject or object.
        
        Args:
            old_urn: Old document URN
            new_urn: New document URN
            
        Raises:
            Exception: If index update fails
        """
        import tantivy
        writer = None
        try:
            writer = self.graph_search_index.get_writer()
            
            # Search for all triples containing the old URN
            searcher = self.graph_search_index.index.searcher()
            
            # Import Occur enum for boolean operations
            try:
                from tantivy import Occur
            except ImportError:
                Occur = self.graph_search_index.tantivy.Occur
            
            # Find triples where old URN is subject
            subject_query = tantivy.Query.term_query(self.graph_search_index.schema, "subject", old_urn)
            subject_results = searcher.search(subject_query, limit=10000)
            
            # Find triples where old URN is object  
            object_query = tantivy.Query.term_query(self.graph_search_index.schema, "object", old_urn)
            object_results = searcher.search(object_query, limit=10000)
            
            # Process subject matches (old URN is subject)
            for score, doc_address in subject_results.hits:
                doc = searcher.doc(doc_address)
                predicate = doc.get_first("predicate")
                object_val = doc.get_first("object")
                triple_type = doc.get_first("triple_type")
                
                if predicate and object_val and triple_type:
                    # Delete old triple
                    self.graph_search_index.delete_triple(writer, old_urn, predicate, object_val, triple_type)
                    # Add new triple with updated subject
                    self.graph_search_index.add_triple(writer, new_urn, predicate, object_val, triple_type)
            
            # Process object matches (old URN is object)
            for score, doc_address in object_results.hits:
                doc = searcher.doc(doc_address)
                subject = doc.get_first("subject")
                predicate = doc.get_first("predicate")
                triple_type = doc.get_first("triple_type")
                
                if subject and predicate and triple_type:
                    # Skip if this was already processed in subject matches
                    if subject != old_urn:
                        # Delete old triple
                        self.graph_search_index.delete_triple(writer, subject, predicate, old_urn, triple_type)
                        # Add new triple with updated object
                        self.graph_search_index.add_triple(writer, subject, predicate, new_urn, triple_type)
            
            # Commit changes
            writer.commit()
            writer = None  # Prevent double-commit in finally block
            
        except Exception as e:
            self.logger.error(f"Tantivy graph index move update failed: {old_urn} -> {new_urn}: {e}")
            raise
        finally:
            if writer:
                try:
                    writer.commit()
                    self.logger.warning(f"Committed writer after exception for graph move {old_urn} -> {new_urn}")
                except Exception as e_commit:
                    self.logger.error(f"Failed to commit writer after exception: {e_commit}")