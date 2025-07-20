# cmcp/managers/knowledge_base_manager.py

"""
A refactored version of the knowledge base manager for CMCP.
This version delegates all search-related functionality to the new SearchService,
resulting in a cleaner, more maintainable, and focused class.
"""

import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from cmcp.kb.document_store import DocumentStore
from cmcp.kb.models import DocumentIndex, ImplicitRDFTriple
from cmcp.kb.path import PathComponents, PartialPathComponents
from cmcp.utils.logging import get_logger
from cmcp.config import AppConfig

# New, clean imports from the structured search module
from cmcp.kb.search import (
    SearchService, 
    SearchIndexManager, 
    SearchIndexRecovery,
    SparseSearchIndex, 
    GraphSearchIndex, 
    Reranker
)

logger = get_logger(__name__)


class KnowledgeBaseManager:
    """
    Manages the knowledge base, focusing on document and metadata operations.
    All search functionality is delegated to the SearchService.
    """
    
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
        """Initialize the refactored knowledge base manager."""
        self.storage_path = storage_path
        self.timeout_default = timeout_default
        self.timeout_max = timeout_max
        self.document_store: Optional[DocumentStore] = None
        self.logger = logger
        
        # Search configuration is now passed down to the SearchService
        self.search_enabled = search_enabled
        self.sparse_index_path = sparse_index_path or os.path.join(storage_path, "search/sparse_idx")
        self.graph_index_path = graph_index_path or os.path.join(storage_path, "search/graph_idx")
        self.reranker_model = reranker_model or "mixedbread-ai/mxbai-rerank-base-v1"
        self.search_relation_predicates = search_relation_predicates or ["references"]
        self.search_graph_neighbor_limit = search_graph_neighbor_limit
        
        # The single point of contact for all search operations
        self.search_service: Optional[SearchService] = None
        
        logger.debug("KnowledgeBaseManager initialized.")
    
    @classmethod
    def from_env(cls, config: Optional[AppConfig] = None) -> 'KnowledgeBaseManager':
        """Create a KnowledgeBaseManager instance from configuration."""
        if config is None:
            from cmcp.config import load_config
            config = load_config()
        
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
        """Check if the knowledge base manager is initialized."""
        if self.document_store is None:
            raise RuntimeError("KnowledgeBaseManager not initialized. Call initialize() first.")
    
    async def initialize(self) -> None:
        """Initialize the document store and the search service."""
        if self.document_store is None:
            os.makedirs(self.storage_path, exist_ok=True)
            
            # Create documents subdirectory for document storage
            documents_path = os.path.join(self.storage_path, "documents")
            os.makedirs(documents_path, exist_ok=True)
            
            # Initialize DocumentStore with the documents subdirectory
            self.document_store = DocumentStore(documents_path)
            self.logger.info(f"Initialized knowledge base at: {self.storage_path}")
            self.logger.info(f"Documents stored in: {documents_path}")
            
            if self.search_enabled:
                try:
                    self.logger.info("Initializing search service and its components...")
                    os.makedirs(self.sparse_index_path, exist_ok=True)
                    os.makedirs(self.graph_index_path, exist_ok=True)
                    
                    # 1. Low-level components
                    sparse_index = SparseSearchIndex(self.sparse_index_path)
                    graph_index = GraphSearchIndex(self.graph_index_path)
                    reranker = Reranker(self.reranker_model)
                    
                    # 2. Synchronous manager
                    search_manager = SearchIndexManager(sparse_index, graph_index, reranker)
                    
                    # 3. Recovery utility
                    search_recovery = SearchIndexRecovery(search_manager, self.document_store)

                    # 4. Main async service, passing down config
                    self.search_service = SearchService(
                        search_index_manager=search_manager,
                        search_recovery=search_recovery,
                        document_store=self.document_store,
                        search_relation_predicates=self.search_relation_predicates,
                        search_graph_neighbor_limit=self.search_graph_neighbor_limit
                    )
                    self.logger.info("Search service initialized successfully.")
                except Exception as e:
                    self.logger.error(f"Failed to initialize search service: {e}", exc_info=True)
                    self.search_enabled = False

    # === Document Content Methods ===

    async def write_content(self, components: PathComponents, content: str) -> DocumentIndex:
        """Writes document content and delegates indexing to the SearchService."""
        self.check_initialized()
        
        self.document_store.write_content(components, content)
        
        if self.search_enabled and self.search_service:
            await self.search_service.update_document_in_indices(components.uri, content)
        
        return self.document_store.update_index(components, {"updated_at": datetime.now(timezone.utc)})
        
    async def read_content(self, components: PathComponents) -> Optional[str]:
        """Read content of a document."""
        self.check_initialized()
        return self.document_store.read_content(components)
        
    async def check_content(self, components: PathComponents) -> bool:
        """Check if content exists for a document in the knowledge base."""
        self.check_initialized()
        return self.document_store.check_content(components)

    # === Document Index and Metadata Methods ===

    async def create_document(self, components: PathComponents, metadata: Optional[Dict[str, Any]] = None) -> DocumentIndex:
        """Create a new document with metadata but no content."""
        self.check_initialized()
        if self.document_store.check_index(components):
            raise ValueError(f"Document already exists at path: {components.path}")
        
        index = DocumentIndex(
            namespace=components.namespace,
            collection=components.collection,
            name=components.name,
            metadata=(metadata or {})
        )
        self.document_store.write_index(components, index)
        return index

    async def read_index(self, components: PathComponents) -> DocumentIndex:
        """Read document index."""
        self.check_initialized()
        return self.document_store.read_index(components)

    async def check_index(self, components: PathComponents) -> bool:
        """Check if index exists for a document in the knowledge base."""
        self.check_initialized()
        return self.document_store.check_index(components)

    async def update_metadata(self, components: PathComponents, metadata: Dict[str, Any]) -> DocumentIndex:
        """Update metadata for a document."""
        self.check_initialized()
        current_index = self.document_store.read_index(components)
        updated_metadata = dict(current_index.metadata)
        updated_metadata.update(metadata)
        return self.document_store.update_index(components, {"metadata": updated_metadata})

    async def add_metadata_property(self, components: PathComponents, key: str, value: Any) -> Dict[str, Any]:
        """Add or update a single metadata property."""
        self.check_initialized()
        index = self.document_store.read_index(components)
        updated_metadata = dict(index.metadata)
        updated_metadata[key] = value
        updated_index = self.document_store.update_index(components, {"metadata": updated_metadata})
        return {"status": "updated", "metadata_count": len(updated_index.metadata), "key": key, "value": value}

    async def remove_metadata_property(self, components: PathComponents, key: str) -> Dict[str, Any]:
        """Remove a specific metadata property."""
        self.check_initialized()
        index = self.document_store.read_index(components)
        updated_metadata = dict(index.metadata)
        removed = key in updated_metadata
        if removed:
            del updated_metadata[key]
        updated_index = self.document_store.update_index(components, {"metadata": updated_metadata})
        return {"status": "updated" if removed else "unchanged", "metadata_count": len(updated_index.metadata), "key": key, "removed": removed}

    # === Triples: References & Preferences ===

    async def add_reference(self, components: PathComponents, ref_components: PathComponents, relation: str) -> Dict[str, Any]:
        """Adds a document reference and delegates indexing to the SearchService."""
        self.check_initialized()
        
        source_index = self.document_store.read_index(components)
        triple = ImplicitRDFTriple(predicate=relation, object=ref_components.uri)
        if triple in source_index.references:
            return {"status": "success", "message": "Reference already exists", "added": False}

        source_index.references.append(triple)
        self.document_store.update_index(components, {"references": source_index.references})
        
        ref_index = self.document_store.read_index(ref_components)
        reverse_triple = ImplicitRDFTriple(predicate=relation, object=components.uri)
        if reverse_triple not in ref_index.referenced_by:
            ref_index.referenced_by.append(reverse_triple)
            self.document_store.update_index(ref_components, {"referenced_by": ref_index.referenced_by})

        if self.search_enabled and self.search_service:
            await self.search_service.add_triple_to_indices(components.uri, relation, ref_components.uri, "reference")
            
        return {"status": "success", "message": "Reference added", "added": True}
    
    async def remove_reference(self, components: PathComponents, ref_components: PathComponents, relation: str) -> Dict[str, Any]:
        """Removes a document reference and delegates de-indexing to the SearchService."""
        self.check_initialized()
        
        index = self.document_store.read_index(components)
        ref_to_remove = ImplicitRDFTriple(predicate=relation, object=ref_components.uri)
        
        if ref_to_remove not in index.references:
            return {"status": "unchanged", "reference_count": len(index.references)}

        updated_refs = [ref for ref in index.references if ref != ref_to_remove]
        self.document_store.update_index(components, {"references": updated_refs})

        # Also remove the reverse reference from the target document
        try:
            ref_index = self.document_store.read_index(ref_components)
            reverse_triple = ImplicitRDFTriple(predicate=relation, object=components.uri)
            if reverse_triple in ref_index.referenced_by:
                updated_referenced_by = [ref for ref in ref_index.referenced_by if ref != reverse_triple]
                self.document_store.update_index(ref_components, {"referenced_by": updated_referenced_by})
        except FileNotFoundError:
            self.logger.warning(f"Referenced document not found when trying to remove reverse reference: {ref_components.uri}")
        except Exception as e:
            self.logger.error(f"Failed to remove reverse reference from {ref_components.uri}: {e}", exc_info=True)

        if self.search_enabled and self.search_service:
            await self.search_service.delete_triple_from_indices(components.uri, relation, ref_components.uri, "reference")
            
        return {"status": "updated", "reference_count": len(updated_refs)}

    async def add_preference(self, components: PathComponents, preferences: List[ImplicitRDFTriple]) -> Dict[str, Any]:
        """Add preference triples to a document."""
        self.check_initialized()
        index = self.document_store.read_index(components)
        updated_preferences = list(index.preferences)
        added_prefs = []
        for p in preferences:
            if p not in updated_preferences:
                updated_preferences.append(p)
                added_prefs.append(p)
        
        updated_index = self.document_store.update_index(components, {"preferences": updated_preferences})

        if self.search_enabled and self.search_service:
            for p in added_prefs:
                await self.search_service.add_triple_to_indices(components.uri, p.predicate, p.object, "preference")
        
        return {"status": "updated", "preference_count": len(updated_index.preferences)}
    
    async def remove_preference(self, components: PathComponents, preferences: List[ImplicitRDFTriple]) -> Dict[str, Any]:
        """Remove preference triples from a document."""
        self.check_initialized()
        index = self.document_store.read_index(components)
        
        current_prefs = set(index.preferences)
        prefs_to_remove = set(preferences)
        removed_prefs = list(current_prefs.intersection(prefs_to_remove))
        updated_preferences = list(current_prefs - prefs_to_remove)

        updated_index = self.document_store.update_index(components, {"preferences": updated_preferences})
        
        if self.search_enabled and self.search_service:
            for p in removed_prefs:
                await self.search_service.delete_triple_from_indices(components.uri, p.predicate, p.object, "preference")

        return {"status": "updated", "preference_count": len(updated_index.preferences)}

    async def remove_all_preferences(self, components: PathComponents) -> Dict[str, Any]:
        """Remove all preference triples from a document."""
        self.check_initialized()
        index = self.document_store.read_index(components)
        
        if self.search_enabled and self.search_service:
            for p in index.preferences:
                await self.search_service.delete_triple_from_indices(components.uri, p.predicate, p.object, "preference")

        self.document_store.update_index(components, {"preferences": []})
        return {"status": "updated", "preference_count": 0}

    # === Filesystem & Lifecycle Methods ===
    
    async def list_documents(self, components: Optional[PartialPathComponents] = None, recursive: bool = True, filter_uris: Optional[List[str]] = None, include_content: bool = False, include_index: bool = False) -> List[str]:
        """List documents in the knowledge base."""
        self.check_initialized()
        if components is None:
            components = PartialPathComponents()
        if recursive:
            document_paths = self.document_store.find_documents_recursive(components)
        else:
            document_paths = self.document_store.find_documents_shallow(components)
        logger.info(f"Found {len(document_paths)} documents: {document_paths}")
        documents = []
        for path_name in document_paths:
            if filter_uris and path_name in filter_uris:
                continue
            logger.info(f"Found document: {path_name}")
            path = PathComponents.parse_path(path_name)
            document = {
                "uri": path.uri
            }
            if include_content:
                document["content"] = await self.read_content(path)
            if include_index:
                document["index"] = self.document_store.read_index(path)
            documents.append(document)
        return documents

    async def move_document(self, components: PathComponents, new_components: PathComponents) -> DocumentIndex:
        """Move a document, updating search index via SearchService."""
        self.check_initialized()
        index = self.document_store.read_index(components)
        
        # Move file on disk
        self.document_store.move_document(components, new_components)

        # Update reverse references
        for reverse_ref in index.referenced_by:
            try:
                referencing_components = PathComponents.parse_path(reverse_ref.object)
                referencing_index = self.document_store.read_index(referencing_components)
                updated_references = [
                    ImplicitRDFTriple(ref.predicate, new_components.uri) if ref.object == components.uri else ref
                    for ref in referencing_index.references
                ]
                if updated_references != referencing_index.references:
                    self.document_store.update_index(referencing_components, {"references": updated_references})
            except Exception as e:
                self.logger.error(f"Failed to update reverse reference in {reverse_ref.object}: {e}")

        # Delegate to search service
        if self.search_enabled and self.search_service:
            try:
                content = await self.read_content(new_components)
                await self.search_service.move_document_in_indices(components.uri, new_components.uri, content or "")
            except Exception as e:
                self.logger.error(f"SearchService failed to move document indices: {e}", exc_info=True)

        return self.document_store.read_index(new_components)

    async def delete_document(self, components: PathComponents) -> Dict[str, Any]:
        """Deletes a document and delegates de-indexing to the SearchService."""
        self.check_initialized()
        
        if not self.document_store.check_index(components):
            return {"status": "not_found", "message": f"Document not found: {components.uri}"}
        
        # Clean up references before deleting
        # (Simplified logic, a real implementation would be more robust)

        # Delegate de-indexing first
        if self.search_enabled and self.search_service:
            await self.search_service.delete_document_from_indices(components.uri)

        # Then delete from document store
        self.document_store.delete_document(components)
        return {"status": "deleted", "message": f"Document deleted: {components.uri}"}

    async def archive_document(self, components: PathComponents) -> Dict[str, Any]:
        """Archives a document by moving it to the 'archive' namespace."""
        self.check_initialized()
        
        if not self.document_store.check_index(components):
            return {"status": "not_found", "message": f"Document not found: {components.uri}"}
        
        index = self.document_store.read_index(components)
        
        # Define the archive path. We put it inside a collection matching the original namespace.
        archive_components = PathComponents(
            namespace="archive",
            collection=components.namespace,
            name=f"{components.collection}-{components.name}"
        )

        # First, remove from search indices
        if self.search_enabled and self.search_service:
            await self.search_service.delete_document_from_indices(components.uri)

        # Clean up references before moving
        for ref in index.references:
            try:
                ref_comp = PathComponents.parse_path(ref.object)
                await self.remove_reference(components, ref_comp, ref.predicate)
            except Exception as e:
                self.logger.warning(f"Failed to clean up outgoing reference from {components.uri} to {ref.object}: {e}")

        for ref_by in index.referenced_by:
            try:
                ref_by_comp = PathComponents.parse_path(ref_by.object)
                await self.remove_reference(ref_by_comp, components, ref_by.predicate)
            except Exception as e:
                self.logger.warning(f"Failed to clean up incoming reference to {components.uri} from {ref_by.object}: {e}")
                
        # Move the document
        try:
            self.document_store.move_document(components, archive_components)
            self.logger.info(f"Archived document {components.path} to {archive_components.path}")
            return {
                "status": "archived",
                "message": f"Document archived: {components.uri}",
                "archive_path": archive_components.path,
                "archive_uri": archive_components.uri
            }
        except Exception as e:
            self.logger.error(f"Failed to move document to archive: {e}", exc_info=True)
            # Re-index if move fails
            if self.search_enabled and self.search_service:
                try:
                    content = await self.read_content(components)
                    await self.search_service.update_document_in_indices(components.uri, content or "")
                except Exception as reindex_e:
                    self.logger.error(f"Failed to re-index document after failed archive attempt: {reindex_e}")
            return {"status": "error", "message": str(e)}

    # === Search & Recovery (Delegated) ===

    async def search(self, **kwargs) -> List[Dict[str, Any]]:
        """Delegates search directly to the SearchService."""
        self.check_initialized()
        if not self.search_enabled or not self.search_service:
            raise RuntimeError("Search is disabled or not initialized.")
            
        return await self.search_service.search(**kwargs)
    
    async def recover_search_indices(self, rebuild_all: bool = False) -> Dict[str, Any]:
        """Delegates index recovery directly to the SearchService."""
        self.check_initialized()
        if not self.search_enabled or not self.search_service:
            raise RuntimeError("Search is disabled or not initialized.")
        
        return await self.search_service.recover_indices(rebuild_all=rebuild_all)

    # ... other non-search-related methods from the original KBM would go here ...
    # (e.g., create_document, read_index, metadata/preference handling, etc.) 