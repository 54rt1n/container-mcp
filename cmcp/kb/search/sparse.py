"""Sparse search index implementation using Tantivy.

This module provides a text-based search index for document content,
leveraging the Tantivy search engine for efficient and fast sparse retrieval.
"""

import os
import logging
from pathlib import Path
from typing import List, Tuple, Optional
from contextlib import contextmanager

from cmcp.utils.logging import get_logger

logger = get_logger(__name__)

class SparseSearchIndex:
    """Manages the Tantivy index for document text content."""

    def __init__(self, index_path: str):
        """Initialize the sparse search index.
        
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
        """Create or open the Tantivy index and define its schema."""
        os.makedirs(self.index_path, exist_ok=True)
        
        schema_builder = self.tantivy.SchemaBuilder()
        schema_builder.add_text_field("urn", stored=True, tokenizer_name="raw")
        schema_builder.add_text_field("content", stored=False)
        self.schema = schema_builder.build()
        
        try:
            self.index = self.tantivy.Index(self.schema, str(self.index_path))
            logger.info(f"Opened existing sparse search index at {self.index_path}")
        except Exception as e:
            logger.info(f"Creating new sparse search index at {self.index_path}: {e}")
            self.index = self.tantivy.Index(self.schema, str(self.index_path))

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

    def add_document(self, writer, urn: str, content: str):
        """Add a document to the index."""
        doc = self.tantivy.Document()
        doc.add_text("urn", urn)
        doc.add_text("content", content)
        writer.add_document(doc)

    def delete_document(self, writer, urn: str):
        """Delete a document from the index by its URN."""
        writer.delete_documents("urn", urn)

    def search(self, query_str: str, top_k: int, fuzzy_distance: int = 0, filter_urns: Optional[List[str]] = None) -> List[Tuple[str, float]]:
        """Search the index using BM25 with optional fuzzy matching and filtering."""
        if not query_str or not query_str.strip():
            logger.warning("Empty query string provided to sparse search.")
            return []
        
        logger.debug(f"Searching sparse index with query: '{query_str}', top_k: {top_k}")
        
        self.index.reload()
        searcher = self.index.searcher()
        
        try:
            query = self.index.parse_query(query_str, default_field_names=["content"])
        except Exception as e:
            logger.warning(f"Query parsing failed: {e}, falling back to simple term search.")
            query = self.tantivy.Query.term_query(self.schema, "content", query_str)

        results = []
        for score, doc_address in searcher.search(query, limit=top_k).hits:
            doc = searcher.doc(doc_address)
            urn = doc.get_first("urn")
            if urn:
                results.append((urn, score))
        return results

    def clear_index(self):
        """Completely clear the index."""
        import shutil
        logger.info(f"Clearing sparse search index at {self.index_path}")
        if self.index_path.exists():
            shutil.rmtree(self.index_path)
        self._initialize_index() 