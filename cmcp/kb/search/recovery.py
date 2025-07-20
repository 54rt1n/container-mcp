"""Search index recovery and rebuilding implementation."""

import asyncio
from typing import Dict, Any

from cmcp.kb.path import PathComponents
from cmcp.utils.logging import get_logger

logger = get_logger(__name__)


class SearchIndexRecovery:
    """Handles recovery and rebuilding of search indices."""

    def __init__(self, search_index_manager, document_store):
        self.search_index_manager = search_index_manager
        self.document_store = document_store

    async def recover_indices(self, rebuild_all: bool = False) -> Dict[str, Any]:
        """Recovers or rebuilds search indices."""
        status = {
            "sparse_index": {"status": "skipped", "error": None},
            "graph_index": {"status": "skipped", "error": None},
            "documents_processed": 0,
            "triples_processed": 0
        }

        if rebuild_all:
            logger.info("Starting full index rebuild...")
            await self._clear_indices_for_rebuild(status)
            await self._rebuild_indices_from_documents(status)
            status["sparse_index"]["status"] = "rebuilt"
            status["graph_index"]["status"] = "rebuilt"
            logger.info("Index rebuild completed.")
        else:
            logger.info("Starting index recovery...")
            # Recover sparse index
            try:
                await asyncio.to_thread(self.search_index_manager.sparse_index._recover_index)
                status["sparse_index"]["status"] = "recovered"
            except Exception as e:
                status["sparse_index"]["status"] = "error"
                status["sparse_index"]["error"] = str(e)
            
            # Recover graph index
            try:
                await asyncio.to_thread(self.search_index_manager.graph_index._recover_index)
                status["graph_index"]["status"] = "recovered"
            except Exception as e:
                status["graph_index"]["status"] = "error"
                status["graph_index"]["error"] = str(e)

        return status

    async def _rebuild_indices_from_documents(self, status: Dict[str, Any]):
        """Rebuilds indices from all existing documents in the document store."""
        all_docs = await self.document_store.list_documents(recursive=True)
        docs_processed = 0
        triples_processed = 0

        for doc_path in all_docs:
            try:
                components = PathComponents.parse_path(doc_path)
                if components.namespace == "archive":
                    continue

                index = await self.document_store.read_index(components)
                content = await self.document_store.read_content(components)

                if content:
                    await asyncio.to_thread(
                        self.search_index_manager.update_sparse_index, components.uri, content
                    )

                for ref in index.references:
                    await asyncio.to_thread(
                        self.search_index_manager.add_triple,
                        components.uri, ref.predicate, ref.object, "reference"
                    )
                    triples_processed += 1
                
                for pref in index.preferences:
                    await asyncio.to_thread(
                        self.search_index_manager.add_triple,
                        components.uri, pref.predicate, pref.object, "preference"
                    )
                    triples_processed += 1
                
                docs_processed += 1
            except Exception as e:
                logger.warning(f"Failed to rebuild index for {doc_path}: {e}")
        
        status["documents_processed"] = docs_processed
        status["triples_processed"] = triples_processed

    async def _clear_indices_for_rebuild(self, status: Dict[str, Any]):
        """Clears all search indices for a fresh rebuild."""
        try:
            await asyncio.to_thread(self.search_index_manager.sparse_index.clear_index)
            status["sparse_cleared"] = True
        except Exception as e:
            status["sparse_cleared"] = False
            status["sparse_index"]["error"] = f"Clear failed: {e}"

        try:
            await asyncio.to_thread(self.search_index_manager.graph_index.clear_index)
            status["graph_cleared"] = True
        except Exception as e:
            status["graph_cleared"] = False
            status["graph_index"]["error"] = f"Clear failed: {e}"

    # For test compatibility
    async def clear_indices(self, status: Dict[str, Any]):
        """Alias for _clear_indices_for_rebuild for test compatibility."""
        await self._clear_indices_for_rebuild(status)

    async def rebuild_indices_from_documents(self, status: Dict[str, Any]):
        """Alias for _rebuild_indices_from_documents for test compatibility."""
        await self._rebuild_indices_from_documents(status) 