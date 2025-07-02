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
        self.tantivy = tantivy  # Store reference for recovery
        self._initialize_index()
    
    def _initialize_index(self):
        """Initialize or reinitialize the Tantivy index."""
        os.makedirs(self.index_path, exist_ok=True)
        
        # Define schema for document content using SchemaBuilder
        schema_builder = self.tantivy.SchemaBuilder()
        schema_builder.add_text_field("urn", stored=True, tokenizer_name="raw")  # Store URN for retrieval, no tokenization
        schema_builder.add_text_field("content", stored=False)  # Don't store content to avoid duplication
        self.schema = schema_builder.build()
        
        # Create or open the index
        try:
            self.index = self.tantivy.Index(self.schema, str(self.index_path))
            logger.info(f"Opened existing sparse search index at {self.index_path}")
        except Exception as e:
            logger.info(f"Creating new sparse search index at {self.index_path}: {e}")
            self.index = self.tantivy.Index(self.schema, str(self.index_path))
    
    def _is_index_healthy(self) -> bool:
        """Check if the index is healthy and can create a writer.
        
        Returns:
            True if index is healthy, False otherwise
        """
        try:
            # Try to create and immediately close a writer
            writer = self.index.writer()
            writer.commit()
            return True
        except Exception as e:
            logger.warning(f"Index health check failed: {e}")
            return False
    
    def _recover_index(self):
        """Recover the index by reinitializing it."""
        logger.info(f"Recovering sparse search index at {self.index_path}")
        try:
            self._initialize_index()
            logger.info(f"Successfully recovered sparse search index")
        except Exception as e:
            logger.error(f"Failed to recover sparse search index: {e}")
            raise
    
    def get_writer(self):
        """Get an index writer.
        
        Returns:
            Tantivy IndexWriter
            
        Raises:
            Exception: If writer cannot be created even after recovery attempt
        """
        try:
            return self.index.writer()
        except Exception as e:
            logger.warning(f"Failed to get writer, attempting index recovery: {e}")
            # Try to recover the index
            self._recover_index()
            # Try again after recovery
            return self.index.writer()
    
    def reload_index(self):
        """Reload the index to see the latest changes."""
        try:
            self.index.reload()
        except Exception as e:
            logger.warning(f"Failed to reload index, attempting recovery: {e}")
            self._recover_index()
    
    def add_document(self, writer, urn: str, content: str):
        """Add a document to the index.
        
        Args:
            writer: Tantivy IndexWriter
            urn: Document URN
            content: Document content
        """
        # Create a proper Tantivy document
        doc = self.tantivy.Document()
        doc.add_text("urn", urn)
        doc.add_text("content", content)
        writer.add_document(doc)
    
    def delete_document(self, writer, urn: str):
        """Delete a document from the index by URN.
        
        Args:
            writer: Tantivy IndexWriter
            urn: Document URN to delete
        """
        writer.delete_documents("urn", urn)
    
    def search(self, query_str: str, top_k: int, fuzzy_distance: int = 0, filter_urns: Optional[List[str]] = None) -> List[Tuple[str, float]]:
        """Search the index using BM25 with optional fuzzy matching.
        
        Args:
            query_str: Query string
            top_k: Maximum number of results to return
            fuzzy_distance: Maximum edit distance for fuzzy matching (0 = exact, 1-2 recommended)
            filter_urns: List of URNs to exclude from results
            
        Returns:
            List of (urn, score) tuples
        """
        if not query_str or not query_str.strip():
            logger.warning("Empty query string provided to sparse search")
            return []
            
        logger.debug(f"Performing sparse search with query: '{query_str}', top_k: {top_k}, fuzzy_distance: {fuzzy_distance}, filter_urns: {len(filter_urns) if filter_urns else 0}")
        
        # Convert filter_urns to set for faster lookup
        filter_urns_set = set(filter_urns) if filter_urns else set()
        
        # Reload the index to see latest changes
        self.reload_index()
        
        # Get a searcher directly (rather than through a reader which can be redundant)
        searcher = self.index.searcher()
        try:
            # If fuzzy search is requested and query is a single term, use fuzzy query
            if fuzzy_distance > 0 and len(query_str.strip().split()) == 1:
                logger.debug(f"Using fuzzy search with distance {fuzzy_distance}")
                query = self.tantivy.Query.fuzzy_term_query(
                    self.schema, "content", query_str.strip(), 
                    distance=fuzzy_distance, 
                    transposition_cost_one=True,
                    prefix=False
                )
            else:
                # Use standard query parsing for multi-term queries or exact search
                try:
                    query = self.index.parse_query(query_str, default_field_names=["content"])
                except Exception as e:
                    logger.warning(f"Query parsing failed: {e}, falling back to simple term search")
                    # Fallback to simple term query if parsing fails
                    words = query_str.strip().split()
                    if len(words) == 1:
                        query = self.tantivy.Query.term_query(self.schema, "content", words[0])
                    else:
                        # For multi-word fallback, try phrase query
                        query = self.tantivy.Query.phrase_query(
                            self.schema, "content", words, slop=2
                        )
            
            # Apply URN filtering using boolean query if filter_urns provided
            if filter_urns_set:
                try:
                    from tantivy import Occur
                except ImportError:
                    Occur = self.tantivy.Occur
                
                # Create a query to exclude filtered URNs
                exclude_query = self.tantivy.Query.term_set_query(self.schema, "urn", list(filter_urns_set))
                
                # Combine original query with exclusion using boolean query
                query = self.tantivy.Query.boolean_query([
                    (Occur.Must, query),           # Must match the search query
                    (Occur.MustNot, exclude_query) # Must not match any filtered URNs
                ])
                
                logger.debug(f"Applied URN filter to exclude {len(filter_urns_set)} URNs")
            
            results = searcher.search(query, limit=top_k)
            
            # Convert results to list of (urn, score) tuples
            # results.hits returns tuples of (score, doc_address)
            result_tuples = []
            for score, doc_address in results.hits:
                doc = searcher.doc(doc_address)
                urn = doc.get_first("urn")
                if urn:
                    # Double-check filter in case the boolean query didn't work as expected
                    if not filter_urns_set or urn not in filter_urns_set:
                        result_tuples.append((urn, score))
            
            # If fuzzy search was used but yielded few results, try a regular search as backup
            if fuzzy_distance > 0 and len(result_tuples) < max(1, top_k // 4):
                logger.debug("Fuzzy search yielded few results, adding exact matches")
                try:
                    exact_query = self.index.parse_query(query_str, default_field_names=["content"])
                    
                    # Apply same URN filtering to exact query
                    if filter_urns_set:
                        try:
                            from tantivy import Occur
                        except ImportError:
                            Occur = self.tantivy.Occur
                        
                        exclude_query = self.tantivy.Query.term_set_query(self.schema, "urn", list(filter_urns_set))
                        exact_query = self.tantivy.Query.boolean_query([
                            (Occur.Must, exact_query),
                            (Occur.MustNot, exclude_query)
                        ])
                    
                    exact_results = searcher.search(exact_query, limit=top_k)
                    
                    # Add exact results that aren't already in fuzzy results
                    existing_urns = {urn for urn, _ in result_tuples}
                    for score, doc_address in exact_results.hits:
                        doc = searcher.doc(doc_address)
                        urn = doc.get_first("urn")
                        if urn and urn not in existing_urns:
                            # Double-check filter
                            if not filter_urns_set or urn not in filter_urns_set:
                                result_tuples.append((urn, score))
                    
                    # Re-sort combined results by score
                    result_tuples.sort(key=lambda x: x[1], reverse=True)
                    result_tuples = result_tuples[:top_k]  # Limit to top_k
                    
                except Exception as e:
                    logger.warning(f"Exact search backup failed: {e}")
            
            # Log some statistics about the results
            if result_tuples:
                min_score = min(score for _, score in result_tuples)
                max_score = max(score for _, score in result_tuples)
                search_type = "fuzzy" if fuzzy_distance > 0 else "exact"
                filter_msg = f", filtered out {len(filter_urns_set)} URNs" if filter_urns_set else ""
                logger.debug(f"Found {len(result_tuples)} {search_type} results with score range: {min_score:.3f} to {max_score:.3f}{filter_msg}")
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
        self.tantivy = tantivy  # Store reference for recovery
        self._initialize_index()
    
    def _initialize_index(self):
        """Initialize or reinitialize the Tantivy index."""
        os.makedirs(self.index_path, exist_ok=True)
        
        # Define schema for RDF triples using SchemaBuilder
        schema_builder = self.tantivy.SchemaBuilder()
        schema_builder.add_text_field("subject", stored=True, tokenizer_name="raw")
        schema_builder.add_text_field("predicate", stored=True, tokenizer_name="raw")
        schema_builder.add_text_field("object", stored=True, tokenizer_name="raw")
        schema_builder.add_text_field("triple_type", stored=True, tokenizer_name="raw")
        self.schema = schema_builder.build()
        
        # Create or open the index
        try:
            self.index = self.tantivy.Index(self.schema, str(self.index_path))
            logger.info(f"Opened existing graph search index at {self.index_path}")
        except Exception as e:
            logger.info(f"Creating new graph search index at {self.index_path}: {e}")
            self.index = self.tantivy.Index(self.schema, str(self.index_path))
    
    def _is_index_healthy(self) -> bool:
        """Check if the index is healthy and can create a writer.
        
        Returns:
            True if index is healthy, False otherwise
        """
        try:
            # Try to create and immediately close a writer
            writer = self.index.writer()
            writer.commit()
            return True
        except Exception as e:
            logger.warning(f"Index health check failed: {e}")
            return False
    
    def _recover_index(self):
        """Recover the index by reinitializing it."""
        logger.info(f"Recovering graph search index at {self.index_path}")
        try:
            self._initialize_index()
            logger.info(f"Successfully recovered graph search index")
        except Exception as e:
            logger.error(f"Failed to recover graph search index: {e}")
            raise
    
    def get_writer(self):
        """Get an index writer.
        
        Returns:
            Tantivy IndexWriter
            
        Raises:
            Exception: If writer cannot be created even after recovery attempt
        """
        try:
            return self.index.writer()
        except Exception as e:
            logger.warning(f"Failed to get writer, attempting index recovery: {e}")
            # Try to recover the index
            self._recover_index()
            # Try again after recovery
            return self.index.writer()
    
    def reload_index(self):
        """Reload the index to see the latest changes."""
        try:
            self.index.reload()
        except Exception as e:
            logger.warning(f"Failed to reload index, attempting recovery: {e}")
            self._recover_index()
    
    def add_triple(self, writer, subject: str, predicate: str, object: str, triple_type: str):
        """Add a triple to the index.
        
        Args:
            writer: Tantivy IndexWriter
            subject: Subject URN
            predicate: Predicate
            object: Object URN
            triple_type: Type of triple (e.g., 'preference', 'reference')
        """
        # Create a proper Tantivy document
        doc = self.tantivy.Document()
        doc.add_text("subject", subject)
        doc.add_text("predicate", predicate)
        doc.add_text("object", object)
        doc.add_text("triple_type", triple_type)
        writer.add_document(doc)
    
    def delete_triple(self, writer, subject: str, predicate: str, object: str, triple_type: str):
        """Delete a specific triple from the index.
        
        Uses boolean query to precisely match and delete only the exact triple.
        
        Args:
            writer: Tantivy IndexWriter
            subject: Subject URN
            predicate: Predicate
            object: Object URN
            triple_type: Type of triple
        """
        # Build a boolean query to match the exact triple
        subject_query = self.tantivy.Query.term_query(self.schema, "subject", subject)
        predicate_query = self.tantivy.Query.term_query(self.schema, "predicate", predicate)
        object_query = self.tantivy.Query.term_query(self.schema, "object", object)
        type_query = self.tantivy.Query.term_query(self.schema, "triple_type", triple_type)
        
        # Import Occur enum for boolean operations
        try:
            from tantivy import Occur
        except ImportError:
            # Fallback if Occur is not directly importable
            Occur = self.tantivy.Occur
        
        # Combine all conditions with AND - all must match for precise deletion
        boolean_query = self.tantivy.Query.boolean_query([
            (Occur.Must, subject_query),
            (Occur.Must, predicate_query),
            (Occur.Must, object_query),
            (Occur.Must, type_query)
        ])
        
        # Delete documents matching the exact triple
        writer.delete_documents_by_query(boolean_query)
        logger.debug(f"Precisely deleted triple: {subject} -{predicate}-> {object} [{triple_type}]")
    
    def find_neighbors(self, urns: List[str], relation_predicates: List[str] = ["references"], 
                       neighbor_limit: int = 1000, filter_urns: Optional[List[str]] = None) -> Set[str]:
        """Find neighbor nodes connected via specified relations.
        
        Uses optimized term set queries and boolean combinations for efficiency.
        
        Args:
            urns: List of URNs to find neighbors for
            relation_predicates: List of predicates to follow
            neighbor_limit: Maximum number of neighbors to return
            filter_urns: List of URNs to exclude from neighbor results
            
        Returns:
            Set of neighbor URNs
        """
        if not urns:
            logger.debug("No URNs provided for find_neighbors, returning empty set")
            return set()
            
        logger.debug(f"Finding neighbors for {len(urns)} URNs with predicates: {relation_predicates}, filter_urns: {len(filter_urns) if filter_urns else 0}")
        
        # Convert filter_urns to set for faster lookup
        filter_urns_set = set(filter_urns) if filter_urns else set()
        
        # Reload index to see latest changes
        self.reload_index()
        
        # Get a searcher directly
        searcher = self.index.searcher()
        try:
            # Import Occur enum for boolean operations
            try:
                from tantivy import Occur
            except ImportError:
                Occur = self.tantivy.Occur
            
            # Create efficient term set queries for multiple URNs and predicates
            subject_query = self.tantivy.Query.term_set_query(self.schema, "subject", urns)
            object_query = self.tantivy.Query.term_set_query(self.schema, "object", urns)
            predicate_query = self.tantivy.Query.term_set_query(self.schema, "predicate", relation_predicates)
            
            # Find documents where input URN is subject AND predicate matches (forward relations)
            forward_query = self.tantivy.Query.boolean_query([
                (Occur.Must, subject_query),
                (Occur.Must, predicate_query)
            ])
            
            # Find documents where input URN is object AND predicate matches (reverse relations)
            reverse_query = self.tantivy.Query.boolean_query([
                (Occur.Must, object_query),
                (Occur.Must, predicate_query)
            ])
            
            # Combine forward and reverse with OR - we want either direction
            combined_query = self.tantivy.Query.boolean_query([
                (Occur.Should, forward_query),
                (Occur.Should, reverse_query)
            ])
            
            # Single efficient search instead of multiple individual searches
            results = searcher.search(combined_query, limit=neighbor_limit)
            
            # Extract neighbor URNs from results
            neighbors = set()
            input_urns_set = set(urns)  # Convert to set for faster lookup
            
            for score, doc_address in results.hits:
                doc = searcher.doc(doc_address)
                subject = doc.get_first("subject")
                object_val = doc.get_first("object")
                
                # Add the "other end" of the relationship as a neighbor
                if subject in input_urns_set and object_val not in input_urns_set:
                    # Forward relation: input_urn -> neighbor_urn
                    # Apply filter_urns check
                    if not filter_urns_set or object_val not in filter_urns_set:
                        neighbors.add(object_val)
                elif object_val in input_urns_set and subject not in input_urns_set:
                    # Reverse relation: neighbor_urn -> input_urn
                    # Apply filter_urns check
                    if not filter_urns_set or subject not in filter_urns_set:
                        neighbors.add(subject)
            
            filter_msg = f", filtered out {len(filter_urns_set)} URNs" if filter_urns_set else ""
            logger.debug(f"Found {len(neighbors)} unique neighbor URNs for {len(urns)} input URNs using optimized search{filter_msg}")
            return neighbors
            
        except Exception as e:
            logger.error(f"Error in optimized find_neighbors: {e}")
            # Fallback to original method if the optimized approach fails
            logger.warning("Falling back to individual searches")
            return self._find_neighbors_fallback(urns, relation_predicates, neighbor_limit, searcher, filter_urns_set)
        finally:
            # No explicit close needed for searcher in Tantivy-Py as of latest versions
            pass
    
    def _find_neighbors_fallback(self, urns: List[str], relation_predicates: List[str], 
                                neighbor_limit: int, searcher, filter_urns_set: Set[str]) -> Set[str]:
        """Fallback method using individual searches if optimized approach fails."""
        neighbors = set()
        
        for urn in urns:
            for predicate in relation_predicates:
                # Search for URN as subject
                try:
                    subject_query = self.tantivy.Query.term_query(self.schema, "subject", urn)
                    subj_results = searcher.search(subject_query, limit=neighbor_limit)
                    for score, doc_address in subj_results.hits:
                        doc = searcher.doc(doc_address)
                        if doc.get_first("predicate") == predicate:
                            object_val = doc.get_first("object")
                            if object_val and object_val not in urns:
                                # Apply filter_urns check
                                if not filter_urns_set or object_val not in filter_urns_set:
                                    neighbors.add(object_val)
                except Exception as e:
                    logger.warning(f"Error in fallback search for subject {urn}: {e}")
                
                # Search for URN as object
                try:
                    object_query = self.tantivy.Query.term_query(self.schema, "object", urn)
                    obj_results = searcher.search(object_query, limit=neighbor_limit)
                    for score, doc_address in obj_results.hits:
                        doc = searcher.doc(doc_address)
                        if doc.get_first("predicate") == predicate:
                            subject = doc.get_first("subject")
                            if subject and subject not in urns:
                                # Apply filter_urns check
                                if not filter_urns_set or subject not in filter_urns_set:
                                    neighbors.add(subject)
                except Exception as e:
                    logger.warning(f"Error in fallback search for object {urn}: {e}")
        
        return neighbors


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