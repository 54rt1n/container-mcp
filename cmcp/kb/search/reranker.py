"""Reranker implementation for search results.

This module provides a Reranker class that uses a Sentence Transformers
CrossEncoder model to improve the relevance of search results.
"""

import logging
from typing import List, Dict, Any

from cmcp.utils.logging import get_logger

logger = get_logger(__name__)

class Reranker:
    """Uses a cross-encoder model to rerank search results.
    
    This class wraps a Sentence Transformers CrossEncoder model to provide a
    simple interface for reranking a list of documents based on their semantic
    similarity to a given query.
    """

    def __init__(self, model_name: str):
        """Initialize the Reranker and load the cross-encoder model.
        
        Args:
            model_name: The name of the cross-encoder model from Hugging Face
                        (e.g., 'mixedbread-ai/mxbai-rerank-base-v1').
                        
        Raises:
            ImportError: If sentence-transformers is not installed.
            Exception: If the model fails to load.
        """
        try:
            from sentence_transformers.cross_encoder import CrossEncoder
        except ImportError:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Install it with 'pip install sentence-transformers'"
            )
        
        try:
            logger.info(f"Loading cross-encoder model: {model_name}")
            self.model = CrossEncoder(model_name)
            logger.info(f"Successfully loaded cross-encoder model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load cross-encoder model {model_name}: {e}", exc_info=True)
            raise

    def rerank(self, query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Reranks documents based on their semantic similarity to the query.
        
        If the query is empty or no documents are provided, this method will
        fall back to sorting by the existing 'sparse_score' if available.
        
        Args:
            query: The search query string.
            documents: A list of document dictionaries. Each dictionary must have
                       a 'content' key for reranking.
            
        Returns:
            A new list of documents, sorted by the calculated 'rerank_score'
            in descending order.
        """
        if not documents:
            logger.debug("No documents provided for reranking, returning empty list.")
            return []

        if not query or not query.strip():
            logger.warning("Empty query provided. Falling back to sparse score sorting.")
            # If no query, sort by existing sparse_score if available, otherwise maintain order.
            return sorted(documents, key=lambda d: d.get("sparse_score", 0.0), reverse=True)

        logger.debug(f"Reranking {len(documents)} documents with query: '{query}'")
        
        # Create pairs of (query, document content) for the model.
        # Use empty string for content if a document is missing the 'content' key.
        pairs = [(query, doc.get('content', '')) for doc in documents]
        
        # Predict similarity scores for each pair.
        scores = self.model.predict(pairs)
        
        # Add the calculated 'rerank_score' to each document.
        for doc, score in zip(documents, scores):
            doc['rerank_score'] = float(score)
        
        # Sort the documents by the new score in descending order.
        reranked_docs = sorted(documents, key=lambda d: d.get('rerank_score', float('-inf')), reverse=True)
        
        if reranked_docs:
            min_score = min(doc['rerank_score'] for doc in reranked_docs)
            max_score = max(doc['rerank_score'] for doc in reranked_docs)
            logger.debug(
                f"Reranked {len(reranked_docs)} documents with scores from "
                f"{min_score:.4f} to {max_score:.4f}."
            )

        return reranked_docs 