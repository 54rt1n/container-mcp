"""Graph search index implementation using Tantivy.

This module provides an index for storing and querying RDF-like triples,
enabling graph-based search and relationship traversal.
"""

import os
import logging
from pathlib import Path
from typing import List, Set, Optional
from contextlib import contextmanager

from cmcp.utils.logging import get_logger

logger = get_logger(__name__)

class GraphSearchIndex:
    """Manages the Tantivy index for RDF triples."""

    def __init__(self, index_path: str):
        """Initialize the graph search index.
        
        Args:
            index_path: Path to the index directory.
        
        Raises:
            ImportError: If tantivy is not installed.
        """
        try:
            import tantivy
        except ImportError:
            raise ImportError("tantivy not installed. Install with 'pip install tantivy'")
            
        self.index_path = Path(index_path)
        self.tantivy = tantivy
        self._initialize_index()

    def _initialize_index(self):
        """Create or open the Tantivy index for triples."""
        os.makedirs(self.index_path, exist_ok=True)
        schema_builder = self.tantivy.SchemaBuilder()
        schema_builder.add_text_field("subject", stored=True, tokenizer_name="raw")
        schema_builder.add_text_field("predicate", stored=True, tokenizer_name="raw")
        schema_builder.add_text_field("object", stored=True, tokenizer_name="raw")
        schema_builder.add_text_field("triple_type", stored=True, tokenizer_name="raw")
        self.schema = schema_builder.build()
        try:
            self.index = self.tantivy.Index(self.schema, str(self.index_path))
            logger.info(f"Opened existing graph search index at {self.index_path}")
        except Exception as e:
            logger.info(f"Creating new graph search index at {self.index_path}: {e}")
            self.index = self.tantivy.Index(self.schema, str(self.index_path), reuse=True)
    
    @contextmanager
    def get_writer(self):
        """Provide a transactional writer for index operations."""
        writer = self.index.writer()
        try:
            yield writer
            writer.commit()
        except Exception:
            writer.rollback()
            raise

    def add_triple(self, writer, subject: str, predicate: str, object: str, triple_type: str):
        """Add an RDF triple to the index."""
        doc = self.tantivy.Document()
        doc.add_text("subject", subject)
        doc.add_text("predicate", predicate)
        doc.add_text("object", object)
        doc.add_text("triple_type", triple_type)
        writer.add_document(doc)

    def delete_triple(self, writer, subject: str, predicate: str, object: str, triple_type: str):
        """Delete a specific triple from the index."""
        from tantivy import Occur
        term_queries = [
            (Occur.Must, self.tantivy.Query.term_query(self.schema, "subject", subject)),
            (Occur.Must, self.tantivy.Query.term_query(self.schema, "predicate", predicate)),
            (Occur.Must, self.tantivy.Query.term_query(self.schema, "object", object)),
            (Occur.Must, self.tantivy.Query.term_query(self.schema, "triple_type", triple_type))
        ]
        query = self.tantivy.Query.boolean_query(term_queries)
        writer.delete_documents_by_query(query)
        
    def find_neighbors(self, uris: List[str], relation_predicates: List[str] = ["references"], neighbor_limit: int = 1000, filter_uris: Optional[List[str]] = None) -> Set[str]:
        """Find neighbors of given URIs based on specified relations."""
        if not uris:
            return set()
        
        self.index.reload()
        searcher = self.index.searcher()
        
        uri_query_forward = self.tantivy.Query.term_set_query(self.schema, "subject", uris)
        uri_query_backward = self.tantivy.Query.term_set_query(self.schema, "object", uris)
        pred_query = self.tantivy.Query.term_set_query(self.schema, "predicate", relation_predicates)

        from tantivy import Occur
        
        forward_query = self.tantivy.Query.boolean_query([
            (Occur.Must, uri_query_forward),
            (Occur.Must, pred_query)
        ])
        backward_query = self.tantivy.Query.boolean_query([
            (Occur.Must, uri_query_backward),
            (Occur.Must, pred_query)
        ])
        full_query = self.tantivy.Query.boolean_query([
            (Occur.Should, forward_query),
            (Occur.Should, backward_query)
        ])
        
        neighbors = set()
        for _, doc_address in searcher.search(full_query, limit=neighbor_limit).hits:
            doc = searcher.doc(doc_address)
            subj = doc.get_first("subject")
            obj = doc.get_first("object")
            
            if subj in uris:
                neighbors.add(obj)
            elif obj in uris:
                neighbors.add(subj)
                
        return neighbors - set(uris)

    def delete_document(self, writer, uri: str):
        """Delete all triples associated with a given document URI."""
        from tantivy import Occur
        subject_query = self.tantivy.Query.term_query(self.schema, "subject", uri)
        object_query = self.tantivy.Query.term_query(self.schema, "object", uri)
        
        query = self.tantivy.Query.boolean_query([
            (Occur.Should, subject_query),
            (Occur.Should, object_query)
        ])
        writer.delete_documents_by_query(query)

    def clear_index(self):
        """Completely clear the index."""
        import shutil
        logger.info(f"Clearing graph search index at {self.index_path}")
        if self.index_path.exists():
            shutil.rmtree(self.index_path)
        self._initialize_index()

    def update_moved_document(self, old_uri: str, new_uri: str):
        """Update all triples when a document's URI changes."""
        # This is a complex operation that requires searching for all triples
        # involving the old URI and then re-indexing them with the new URI.
        with self.get_writer() as writer:
            searcher = self.index.searcher()
            
            # Find all triples where the old URI is the subject or object
            from tantivy import Occur
            subject_query = self.tantivy.Query.term_query(self.schema, "subject", old_uri)
            object_query = self.tantivy.Query.term_query(self.schema, "object", old_uri)
            combined_query = self.tantivy.Query.boolean_query([(Occur.Should, subject_query), (Occur.Should, object_query)])
            
            docs_to_update = []
            for _, doc_address in searcher.search(combined_query, limit=10000).hits:
                doc = searcher.doc(doc_address)
                docs_to_update.append(doc.to_dict())

            # Delete old documents and add new ones
            for doc_dict in docs_to_update:
                if doc_dict.get("subject") == [old_uri]:
                    self.delete_triple(writer, old_uri, doc_dict["predicate"][0], doc_dict["object"][0], doc_dict["triple_type"][0])
                    self.add_triple(writer, new_uri, doc_dict["predicate"][0], doc_dict["object"][0], doc_dict["triple_type"][0])
                if doc_dict.get("object") == [old_uri]:
                    self.delete_triple(writer, doc_dict["subject"][0], doc_dict["predicate"][0], old_uri, doc_dict["triple_type"][0])
                    self.add_triple(writer, doc_dict["subject"][0], doc_dict["predicate"][0], new_uri, doc_dict["triple_type"][0]) 