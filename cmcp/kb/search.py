"""Search functionality for the knowledge base.

This module provides Tantivy-based sparse search indexing and
Sentence Transformers cross-encoder reranking for the knowledge base.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from pathlib import Path

from cmcp.utils.logging import get_logger

logger = get_logger(__name__)

class SparseSearchIndex:
    """Manages the Tantivy index for document text content."""
    
    def __init__(self, index_path: str):
        """Initialize the sparse search index.
        
        Args:
            index_path: Path to the index directory
        """
        try:
            import tantivy
        except ImportError:
            raise ImportError("tantivy not installed. Install with 'pip install tantivy'")
        
        self.index_path = Path(index_path)
        os.makedirs(self.index_path, exist_ok=True)
        
        # Define schema for document content using SchemaBuilder
        schema_builder = tantivy.SchemaBuilder()
        schema_builder.add_text_field("urn", stored=True, tokenizer_name="raw")  # Store URN for retrieval, no tokenization
        schema_builder.add_text_field("content", stored=False)  # Don't store content to avoid duplication
        self.schema = schema_builder.build()
        
        # Create or open the index
        try:
            self.index = tantivy.Index(self.schema, str(self.index_path))
            logger.info(f"Opened existing sparse search index at {index_path}")
        except Exception as e:
            logger.info(f"Creating new sparse search index at {index_path}: {e}")
            self.index = tantivy.Index(self.schema, str(self.index_path))
    
    def get_writer(self):
        """Get an index writer.
        
        Returns:
            Tantivy IndexWriter
        """
        return self.index.writer()
    
    def reload_index(self):
        """Reload the index to see the latest changes."""
        self.index.reload()
    
    def add_document(self, writer, urn: str, content: str):
        """Add a document to the index.
        
        Args:
            writer: Tantivy IndexWriter
            urn: Document URN
            content: Document content
        """
        doc = {"urn": urn, "content": content}
        writer.add_document(doc)
    
    def delete_document(self, writer, urn: str):
        """Delete a document from the index by URN.
        
        Args:
            writer: Tantivy IndexWriter
            urn: Document URN to delete
        """
        writer.delete_documents("urn", urn)
    
    def search(self, query_str: str, top_k: int) -> List[Tuple[str, float]]:
        """Search the index using BM25.
        
        Args:
            query_str: Query string
            top_k: Maximum number of results to return
            
        Returns:
            List of (urn, score) tuples
        """
        if not query_str or not query_str.strip():
            logger.warning("Empty query string provided to sparse search")
            return []
            
        logger.debug(f"Performing sparse search with query: '{query_str}', top_k: {top_k}")
        
        # Reload the index to see latest changes
        self.reload_index()
        
        # Get a searcher directly (rather than through a reader which can be redundant)
        searcher = self.index.searcher()
        try:
            query_parser = self.index.query_parser(["content"])
            query = query_parser.parse(query_str)
            
            results = searcher.search(query, limit=top_k)
            
            # Convert results to list of (urn, score) tuples
            result_tuples = [(hit.doc.get("urn"), hit.score) for hit in results.hits]
            
            # Log some statistics about the results
            if result_tuples:
                min_score = min(score for _, score in result_tuples)
                max_score = max(score for _, score in result_tuples)
                logger.debug(f"Found {len(result_tuples)} results with score range: {min_score:.3f} to {max_score:.3f}")
            else:
                logger.debug("No results found for the query")
                
            return result_tuples
        finally:
            # No explicit close needed for searcher in Tantivy-Py as of latest versions
            pass


class GraphSearchIndex:
    """Manages the Tantivy index for RDF triples."""
    
    def __init__(self, index_path: str):
        """Initialize the graph search index.
        
        Args:
            index_path: Path to the index directory
        """
        try:
            import tantivy
        except ImportError:
            raise ImportError("tantivy not installed. Install with 'pip install tantivy'")
        
        self.index_path = Path(index_path)
        os.makedirs(self.index_path, exist_ok=True)
        
        # Define schema for RDF triples using SchemaBuilder
        schema_builder = tantivy.SchemaBuilder()
        schema_builder.add_text_field("subject", stored=True, tokenizer_name="raw")
        schema_builder.add_text_field("predicate", stored=True, tokenizer_name="raw")
        schema_builder.add_text_field("object", stored=True, tokenizer_name="raw")
        schema_builder.add_text_field("triple_type", stored=True, tokenizer_name="raw")
        self.schema = schema_builder.build()
        
        # Create or open the index
        try:
            self.index = tantivy.Index(self.schema, str(self.index_path))
            logger.info(f"Opened existing graph search index at {index_path}")
        except Exception as e:
            logger.info(f"Creating new graph search index at {index_path}: {e}")
            self.index = tantivy.Index(self.schema, str(self.index_path))
    
    def get_writer(self):
        """Get an index writer.
        
        Returns:
            Tantivy IndexWriter
        """
        return self.index.writer()
    
    def reload_index(self):
        """Reload the index to see the latest changes."""
        self.index.reload()
    
    def add_triple(self, writer, subject: str, predicate: str, object: str, triple_type: str):
        """Add a triple to the index.
        
        Args:
            writer: Tantivy IndexWriter
            subject: Subject URN
            predicate: Predicate
            object: Object URN
            triple_type: Type of triple (e.g., 'preference', 'reference')
        """
        import tantivy
        
        # Create a proper Tantivy document
        doc = tantivy.Document()
        doc.add_text("subject", subject)
        doc.add_text("predicate", predicate)
        doc.add_text("object", object)
        doc.add_text("triple_type", triple_type)
        writer.add_document(doc)
    
    def delete_triple(self, writer, subject: str, predicate: str, object: str, triple_type: str):
        """Delete a triple from the index.
        
        Note: Since delete_documents only accepts single field deletions,
        this is a simplified implementation that deletes by subject.
        For exact triple deletion, we'd need to search and delete individually.
        
        Args:
            writer: Tantivy IndexWriter
            subject: Subject URN
            predicate: Predicate
            object: Object URN
            triple_type: Type of triple
        """
        # Since the current Tantivy API doesn't support complex query-based deletion,
        # we delete by subject as a simplified approach
        # This may delete more than intended, but it's better than failing
        logger.warning(f"Deleting triples by subject only: {subject} (simplified deletion)")
        writer.delete_documents("subject", subject)
    
    def find_neighbors(self, urns: List[str], relation_predicates: List[str] = ["references"], 
                       neighbor_limit: int = 1000) -> Set[str]:
        """Find neighbor nodes connected via specified relations.
        
        Args:
            urns: List of URNs to find neighbors for
            relation_predicates: List of predicates to follow
            neighbor_limit: Maximum number of neighbors to return
            
        Returns:
            Set of neighbor URNs
        """
        import tantivy
        
        if not urns:
            logger.debug("No URNs provided for find_neighbors, returning empty set")
            return set()
            
        logger.debug(f"Finding neighbors for {len(urns)} URNs with predicates: {relation_predicates}")
        
        # Reload index to see latest changes
        self.reload_index()
        
        # Get a searcher directly
        searcher = self.index.searcher()
        try:
            # For simplicity, search for each URN individually and combine results
            # This is less efficient but works with the current API
            neighbors = set()
            
            for urn in urns:
                for predicate in relation_predicates:
                    # Search for URN as subject
                    try:
                        subject_query = tantivy.Query.term_query(self.schema, "subject", urn)
                        pred_query = tantivy.Query.term_query(self.schema, "predicate", predicate)
                        # Note: Can't easily combine queries, so search separately
                        subj_results = searcher.search(subject_query, limit=neighbor_limit)
                        for hit in subj_results.hits:
                            doc = hit.doc
                            if doc.get("predicate") == predicate:
                                object_val = doc.get("object")
                                if object_val and object_val not in urns:
                                    neighbors.add(object_val)
                    except Exception as e:
                        logger.warning(f"Error searching for subject {urn} with predicate {predicate}: {e}")
                    
                    # Search for URN as object
                    try:
                        object_query = tantivy.Query.term_query(self.schema, "object", urn)
                        obj_results = searcher.search(object_query, limit=neighbor_limit)
                        for hit in obj_results.hits:
                            doc = hit.doc
                            if doc.get("predicate") == predicate:
                                subject = doc.get("subject")
                                if subject and subject not in urns:
                                    neighbors.add(subject)
                    except Exception as e:
                        logger.warning(f"Error searching for object {urn} with predicate {predicate}: {e}")
            
            logger.debug(f"Found {len(neighbors)} unique neighbor URNs for {len(urns)} input URNs")
            return neighbors
        finally:
            # No explicit close needed for searcher in Tantivy-Py as of latest versions
            pass


class Reranker:
    """Cross-encoder model for reranking search results."""
    
    def __init__(self, model_name: str):
        """Initialize the reranker with a model.
        
        Args:
            model_name: Hugging Face model name for the cross-encoder
        """
        try:
            from sentence_transformers.cross_encoder import CrossEncoder
        except ImportError:
            raise ImportError("sentence-transformers not installed. Install with 'pip install sentence-transformers'")
        
        try:
            logger.info(f"Loading cross-encoder model: {model_name}")
            self.model = CrossEncoder(model_name)
            logger.info(f"Successfully loaded cross-encoder model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load cross-encoder model {model_name}: {e}", exc_info=True)
            raise
    
    def rerank(self, query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rerank documents based on semantic similarity to query.
        
        Args:
            query: Query string
            documents: List of documents with 'urn' and 'content' keys
            
        Returns:
            Reranked documents with rerank_score added
        """
        if not documents:
            logger.debug("No documents provided for reranking, returning empty list")
            return []
            
        if not query or not query.strip():
            logger.warning("Empty query provided for reranking, using sparse scores instead")
            # Sort by sparse score if available, otherwise by URN
            return sorted(documents, 
                          key=lambda x: x.get('sparse_score', float('-inf')), 
                          reverse=True)
        
        logger.debug(f"Reranking {len(documents)} documents with query: '{query}'")
        
        # Create pairs of (query, document content)
        pairs = [(query, doc.get('content', '')) for doc in documents]
        
        # Get similarity scores
        scores = self.model.predict(pairs)
        
        # Add scores to documents
        for doc, score in zip(documents, scores):
            doc['rerank_score'] = float(score)
        
        # Sort by rerank score (descending)
        reranked_docs = sorted(documents, key=lambda x: x['rerank_score'], reverse=True)
        
        # Log some statistics about the reranked results
        if reranked_docs:
            min_score = min(doc['rerank_score'] for doc in reranked_docs)
            max_score = max(doc['rerank_score'] for doc in reranked_docs)
            logger.debug(f"Reranked {len(reranked_docs)} documents with score range: {min_score:.3f} to {max_score:.3f}")
            if len(reranked_docs) > 1:
                top_doc = reranked_docs[0]
                logger.debug(f"Top document: {top_doc.get('urn')} with score {top_doc.get('rerank_score'):.3f}")
        
        return reranked_docs 