"""Search index manager implementation."""

from typing import List, Dict, Any, Tuple, Set, Optional
from contextlib import contextmanager

class SearchIndexManager:
    """Manages synchronous operations across the different search indices.
    
    This class acts as a facade, providing a single point of entry for
    synchronous index operations that will be called from the async
    SearchService. It is responsible for coordinating writes and reads
    across the sparse and graph indices.
    """
    def __init__(self, sparse_index, graph_index, reranker):
        self.sparse_index = sparse_index
        self.graph_index = graph_index
        self.reranker = reranker

    def update_sparse_index(self, urn: str, content: str) -> None:
        """Adds or updates a document in the sparse (text) index."""
        with self.sparse_index.get_writer() as writer:
            self.sparse_index.delete_document(writer, urn)
            self.sparse_index.add_document(writer, urn, content)

    def add_triple(self, subject: str, predicate: str, object_urn: str, triple_type: str) -> None:
        """Adds a triple to the graph index."""
        with self.graph_index.get_writer() as writer:
            self.graph_index.add_triple(writer, subject, predicate, object_urn, triple_type)

    def search_sparse(
        self, query: str, top_k: int, fuzzy_distance: int = 0, filter_urns: Optional[List[str]] = None
    ) -> List[Tuple[str, float]]:
        """Performs a search on the sparse index and returns results."""
        return self.sparse_index.search(query, top_k, fuzzy_distance, filter_urns)

    def delete_sparse_index(self, urn: str) -> None:
        """Deletes a document from the sparse index."""
        with self.sparse_index.get_writer() as writer:
            self.sparse_index.delete_document(writer, urn)

    def delete_triple(self, subject: str, predicate: str, object_urn: str, triple_type: str) -> None:
        """Deletes a specific triple from the graph index."""
        with self.graph_index.get_writer() as writer:
            self.graph_index.delete_triple(writer, subject, predicate, object_urn, triple_type)

    def delete_document_from_graph(self, urn: str) -> None:
        """Deletes all triples associated with a given URN from the graph index."""
        with self.graph_index.get_writer() as writer:
            self.graph_index.delete_document(writer, urn)

    def find_neighbors(
        self, urns: List[str], relation_predicates: List[str], limit: int, filter_urns: Optional[List[str]] = None
    ) -> Set[str]:
        """Finds neighbors in the graph index."""
        return self.graph_index.find_neighbors(urns, relation_predicates, limit, filter_urns)

    def rerank_docs(self, query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Reranks documents using the cross-encoder model."""
        return self.reranker.rerank(query, documents)

    def update_moved_document_sparse(self, old_urn: str, new_urn: str, content: str) -> None:
        """Updates the sparse index when a document's URN changes."""
        with self.sparse_index.get_writer() as writer:
            self.sparse_index.delete_document(writer, old_urn)
            self.sparse_index.add_document(writer, new_urn, content)

    def update_moved_document_graph(self, old_urn: str, new_urn: str) -> None:
        """Updates all graph triples when a document's URN changes."""
        self.graph_index.update_moved_document(old_urn, new_urn)

    def clear_all_indices(self):
        """Clears all data from both sparse and graph indices."""
        self.sparse_index.clear_index()
        self.graph_index.clear_index() 