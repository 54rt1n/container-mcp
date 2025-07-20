"""Search service implementation."""

import asyncio
from typing import List, Dict, Any, Optional, Set, Tuple

from cmcp.kb.path import PathComponents
from cmcp.utils.logging import get_logger

logger = get_logger(__name__)


class SearchService:
    """Orchestrates search operations, acting as the async business logic layer."""

    def __init__(self, search_index_manager, search_recovery, document_store, search_relation_predicates, search_graph_neighbor_limit):
        """Initializes the SearchService.

        Args:
            search_index_manager: The synchronous index manager.
            search_recovery: The index recovery utility.
            document_store: The document storage utility.
            search_relation_predicates: Predicates to follow during graph expansion.
            search_graph_neighbor_limit: Max number of neighbors for graph search.
        """
        self.search_index_manager = search_index_manager
        self.search_recovery = search_recovery
        self.document_store = document_store
        self.reranker = self.search_index_manager.reranker
        self.search_relation_predicates = search_relation_predicates
        self.search_graph_neighbor_limit = search_graph_neighbor_limit

    async def search(self,
                     query: Optional[str] = None,
                     seed_uris: Optional[List[str]] = None,
                     expand_hops: int = 0,
                     relation_predicates: Optional[List[str]] = None,
                     top_k_sparse: int = 50,
                     top_k_rerank: int = 10,
                     filter_uris: Optional[List[str]] = None,
                     include_content: bool = False,
                     include_index: bool = False,
                     use_reranker: bool = True,
                     fuzzy_distance: int = 0) -> List[Dict[str, Any]]:
        """Search the knowledge base using text query and/or graph expansion."""
        if not query and not seed_uris:
            raise ValueError("Search requires either a query or seed_uris.")

        if relation_predicates is None:
            relation_predicates = self.search_relation_predicates

        if not include_content and use_reranker:
            logger.warning("Disabling reranking because include_content=False.")
            use_reranker = False
        
        logger.debug(f"Search request: query='{query}', seed_uris={seed_uris}, hops={expand_hops}")

        candidate_uris, sparse_scores = await self._get_candidate_uris(
            query, seed_uris, expand_hops, relation_predicates, top_k_sparse, filter_uris, fuzzy_distance
        )

        if not candidate_uris:
            return []

        docs_with_data, error_docs = await self._fetch_content_for_candidates(
            candidate_uris, sparse_scores, include_content, include_index, use_reranker, query
        )

        final_results = await self._prepare_final_results(
            query, docs_with_data, error_docs, sparse_scores, use_reranker, top_k_sparse, top_k_rerank
        )

        return final_results

    async def update_document_in_indices(self, uri: str, content: str):
        """Coordinates the update of a document in all relevant search indices."""
        # This will be expanded to include graph updates if necessary.
        await asyncio.to_thread(
            self.search_index_manager.update_sparse_index,
            uri,
            content
        )

    async def delete_document_from_indices(self, uri: str):
        """Coordinates the deletion of a document from all search indices."""
        await asyncio.to_thread(self.search_index_manager.delete_sparse_index, uri)
        await asyncio.to_thread(self.search_index_manager.delete_document_from_graph, uri)

    async def move_document_in_indices(self, old_uri: str, new_uri: str, content: str):
        """Coordinates moving a document in all relevant search indices."""
        await asyncio.to_thread(
            self.search_index_manager.update_moved_document_sparse, old_uri, new_uri, content
        )
        await asyncio.to_thread(
            self.search_index_manager.update_moved_document_graph, old_uri, new_uri
        )

    async def add_triple_to_indices(self, subject: str, predicate: str, object_uri: str, triple_type: str):
        """Adds a triple to the graph index."""
        await asyncio.to_thread(
            self.search_index_manager.add_triple, subject, predicate, object_uri, triple_type
        )

    async def delete_triple_from_indices(self, subject: str, predicate: str, object_uri: str, triple_type: str):
        """Deletes a triple from the graph index."""
        await asyncio.to_thread(
            self.search_index_manager.delete_triple, subject, predicate, object_uri, triple_type
        )

    async def recover_indices(self, rebuild_all: bool = False) -> Dict[str, Any]:
        """Delegates index recovery to the SearchIndexRecovery utility."""
        return await self.search_recovery.recover_indices(rebuild_all=rebuild_all)

    async def _get_candidate_uris(self,
                                  query: Optional[str],
                                  seed_uris: Optional[List[str]],
                                  expand_hops: int,
                                  relation_predicates: List[str],
                                  top_k_sparse: int,
                                  filter_uris: Optional[List[str]],
                                  fuzzy_distance: int = 0) -> Tuple[Set[str], Dict[str, float]]:
        """Get candidate URIs from sparse search and graph expansion."""
        candidate_uris = set(seed_uris or [])
        sparse_scores = {}  # uri -> score

        if query:
            sparse_results = await asyncio.to_thread(
                self.search_index_manager.search_sparse,
                query, top_k_sparse, fuzzy_distance, filter_uris
            )
            for uri, score in sparse_results:
                sparse_scores[uri] = score
                if seed_uris is None or uri in seed_uris:
                    candidate_uris.add(uri)

        if expand_hops > 0 and candidate_uris:
            current_uris = set(candidate_uris)
            all_expanded_uris = set(candidate_uris)
            for _ in range(expand_hops):
                if not current_uris: break
                neighbors = await asyncio.to_thread(
                    self.search_index_manager.find_neighbors,
                    list(current_uris), relation_predicates, self.search_graph_neighbor_limit, filter_uris
                )
                new_uris = neighbors - all_expanded_uris
                all_expanded_uris.update(new_uris)
                current_uris = new_uris
            candidate_uris = all_expanded_uris

        return candidate_uris, sparse_scores

    async def _fetch_content_for_candidates(self,
                                          candidate_uris: Set[str],
                                          sparse_scores: Dict[str, float],
                                          include_content: bool,
                                          include_index: bool,
                                          use_reranker: bool,
                                          query: Optional[str] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Fetch content and/or index for candidate URIs."""
        need_content_for_reranking = use_reranker and query and self.reranker
        fetch_content = include_content or need_content_for_reranking

        docs_with_data, error_docs = [], []

        for uri in candidate_uris:
            try:
                components = PathComponents.parse_path(uri)
                doc_data = {'uri': uri, 'sparse_score': sparse_scores.get(uri)}
                
                content_fetched = False
                if fetch_content:
                    content = await self.document_store.read_content(components)
                    if content:
                        doc_data['content'] = content
                        content_fetched = True

                if include_index:
                    index = await self.document_store.read_index(components)
                    doc_data['index'] = index.model_dump()

                if need_content_for_reranking:
                    if content_fetched:
                        docs_with_data.append(doc_data)
                    else:
                        error_docs.append({'uri': uri, 'error': 'No content for reranking'})
                else:
                    docs_with_data.append(doc_data)

            except Exception as e:
                logger.warning(f"Failed to process {uri}: {e}")
                error_docs.append({'uri': uri, 'error': str(e)})

        return docs_with_data, error_docs

    async def _prepare_final_results(self,
                                   query: Optional[str],
                                   docs_with_data: List[Dict[str, Any]],
                                   error_docs: List[Dict[str, Any]],
                                   sparse_scores: Dict[str, float],
                                   use_reranker: bool,
                                   top_k_sparse: int,
                                   top_k_rerank: int) -> List[Dict[str, Any]]:
        """Prepare final results by reranking or sorting."""
        final_results = list(error_docs)

        if use_reranker and query and docs_with_data and self.reranker:
            reranked_docs = await asyncio.to_thread(
                self.search_index_manager.rerank_docs, query, docs_with_data
            )
            final_results.extend(reranked_docs)
            final_results.sort(key=lambda x: x.get('rerank_score', float('-inf')), reverse=True)
            return final_results[:top_k_rerank]

        if sparse_scores:
            combined = docs_with_data + [res for res in error_docs if res['uri'] not in {d['uri'] for d in docs_with_data}]
            combined.sort(key=lambda x: x.get('sparse_score', float('-inf')), reverse=True)
            return combined[:top_k_sparse]

        if docs_with_data:
            for doc in docs_with_data:
                if 'sparse_score' not in doc:
                    doc['sparse_score'] = 1.0
            docs_with_data.sort(key=lambda x: x['uri'])
            return docs_with_data

        final_results.sort(key=lambda x: x['uri'])
        return final_results[:top_k_rerank] 