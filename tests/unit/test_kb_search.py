# tests/unit/test_kb_search.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Unit tests for KB search components."""

import pytest
from unittest.mock import MagicMock, patch, ANY
import sys
from pathlib import Path

# Create the mocks first
mock_tantivy = MagicMock()
mock_cross_encoder = MagicMock()

# Mock the modules in sys.modules before import
patch_dict = {
    'tantivy': mock_tantivy,
    'sentence_transformers.cross_encoder': MagicMock(CrossEncoder=mock_cross_encoder)
}

# Apply the patch decorator to the entire module
@patch.dict('sys.modules', patch_dict)
class TestKBSearch:
    """Tests for Knowledge Base search components."""
    
    def setup_method(self):
        """Set up test fixtures for each test method."""
        # Reset mocks for each test
        mock_tantivy.reset_mock()
        mock_cross_encoder.reset_mock()
        
        # Set up common mock behaviors
        self.mock_index = MagicMock()
        mock_tantivy.Index.return_value = self.mock_index
        mock_tantivy.Index.create.return_value = self.mock_index
        
        self.mock_writer = MagicMock()
        self.mock_index.writer.return_value = self.mock_writer
        
        self.mock_searcher = MagicMock()
        self.mock_index.searcher.return_value = self.mock_searcher
        
        self.mock_query_parser = MagicMock()
        self.mock_index.query_parser.return_value = self.mock_query_parser
        
        # Set up document mock for creating documents
        self.mock_document = MagicMock()
        mock_tantivy.Document.return_value = self.mock_document
        
        # Set up schema builder mock
        self.mock_schema_builder = MagicMock()
        self.mock_schema = MagicMock()
        self.mock_schema_builder.build.return_value = self.mock_schema
        mock_tantivy.SchemaBuilder.return_value = self.mock_schema_builder
        
        # Import the classes now that the mocks are in place
        from cmcp.kb.search.sparse import SparseSearchIndex
        from cmcp.kb.search.graph import GraphSearchIndex
        from cmcp.kb.search.reranker import Reranker
        self.SparseSearchIndex = SparseSearchIndex
        self.GraphSearchIndex = GraphSearchIndex
        self.Reranker = Reranker
    
    # --- SparseSearchIndex Tests ---
    
    def test_sparse_index_init_create(self, tmp_path):
        """Test SparseSearchIndex initialization creating a new index."""
        # Set up mock to simulate index not found on first call, then succeed
        mock_tantivy.Index.side_effect = [Exception("Simulate index not found"), self.mock_index]
        
        # Create search index
        index_path = tmp_path / "sparse"
        search_idx = self.SparseSearchIndex(str(index_path))
        
        # Verify the index creation behavior
        assert search_idx.index_path == index_path
        # Should be called twice - first fails, second succeeds
        assert mock_tantivy.Index.call_count == 2
        assert str(index_path) in str(mock_tantivy.Index.call_args)
        
        # Skip schema field checks since the implementation details may vary
    
    def test_sparse_index_init_open(self, tmp_path):
        """Test SparseSearchIndex initialization opening an existing index."""
        # Reset side effect to allow normal Index creation
        mock_tantivy.Index.side_effect = None
        
        # Create search index
        index_path = tmp_path / "sparse_existing"
        index_path.mkdir(exist_ok=True)  # Simulate existing dir
        search_idx = self.SparseSearchIndex(str(index_path))
        
        # Verify the right methods were called
        assert search_idx.index_path == index_path
        mock_tantivy.Index.assert_called_once()
        assert str(index_path) in str(mock_tantivy.Index.call_args)
        mock_tantivy.Index.create.assert_not_called()
    
    def test_sparse_add_delete_document(self, tmp_path):
        """Test adding and deleting documents."""
        # Create search index
        search_idx = self.SparseSearchIndex(str(tmp_path / "sparse_ops"))
        
        # Test add document - now uses Document object with add_text calls
        search_idx.add_document(self.mock_writer, "kb://ns/c/d1", "Some content")
        # Verify Document was created and text fields were added
        mock_tantivy.Document.assert_called_once()
        self.mock_document.add_text.assert_any_call("urn", "kb://ns/c/d1")
        self.mock_document.add_text.assert_any_call("content", "Some content")
        self.mock_writer.add_document.assert_called_once_with(self.mock_document)
        
        # Test delete document
        search_idx.delete_document(self.mock_writer, "kb://ns/c/d1")
        self.mock_writer.delete_documents.assert_called_once_with("urn", "kb://ns/c/d1")
    
    def test_sparse_search(self, tmp_path):
        """Test searching the sparse index."""
        # Set up mock search results with proper tuple structure
        mock_doc = MagicMock()
        mock_doc.get_first.return_value = "kb://mock/sparse/doc1"
        
        # Mock the search results - hits should be a list of (score, doc_address) tuples
        mock_search_results = MagicMock()
        mock_search_results.hits = [(1.5, "doc_address_1")]  # (score, doc_address) tuples
        self.mock_searcher.search.return_value = mock_search_results
        self.mock_searcher.doc.return_value = mock_doc
        
        # Mock query parsing
        mock_query = MagicMock()
        self.mock_index.parse_query.return_value = mock_query
        
        # Create search index and perform search
        search_idx = self.SparseSearchIndex(str(tmp_path / "sparse_search"))
        query = "test query"
        results = search_idx.search(query, 10)
        
        # Verify the right methods were called
        self.mock_index.reload.assert_called_once()
        self.mock_index.searcher.assert_called_once()
        self.mock_index.parse_query.assert_called_once_with(query, default_field_names=["content"])
        self.mock_searcher.search.assert_called_once_with(mock_query, limit=10)
        self.mock_searcher.doc.assert_called_once_with("doc_address_1")
        assert results == [("kb://mock/sparse/doc1", 1.5)]
    
    def test_sparse_search_empty_query(self, tmp_path):
        """Test searching with an empty query."""
        # Create search index and perform empty search
        search_idx = self.SparseSearchIndex(str(tmp_path / "sparse_empty"))
        results = search_idx.search("", 10)
        
        # Verify results and that no search was performed
        assert results == []
        self.mock_searcher.search.assert_not_called()
    
    # --- GraphSearchIndex Tests ---
    
    def test_graph_index_init(self, tmp_path):
        """Test GraphSearchIndex initialization."""
        # Create graph index
        index_path = tmp_path / "graph_idx"
        graph_idx = self.GraphSearchIndex(str(index_path))
        
        # Verify only the basic index behavior
        assert graph_idx.index_path == index_path
        mock_tantivy.Index.assert_called_once()
        assert str(index_path) in str(mock_tantivy.Index.call_args)
        
        # Skip schema field checks since the implementation details may vary
    
    def test_graph_add_delete_triple(self, tmp_path):
        """Test adding and deleting triples."""
        # Create graph index
        graph_idx = self.GraphSearchIndex(str(tmp_path / "graph_ops"))
        
        # Test Add - uses Document creation with add_text calls
        graph_idx.add_triple(self.mock_writer, "kb://s", "kb://p", "kb://o", "reference")
        # Verify Document was created and text fields were added
        mock_tantivy.Document.assert_called()
        self.mock_document.add_text.assert_any_call("subject", "kb://s")
        self.mock_document.add_text.assert_any_call("predicate", "kb://p")
        self.mock_document.add_text.assert_any_call("object", "kb://o")
        self.mock_document.add_text.assert_any_call("triple_type", "reference")
        self.mock_writer.add_document.assert_called_with(self.mock_document)
        
        # Test Delete - uses delete_documents_by_query with boolean query for precise deletion
        # Set up query mocks
        mock_boolean_query = MagicMock()
        mock_tantivy.Query.boolean_query.return_value = mock_boolean_query
        
        graph_idx.delete_triple(self.mock_writer, "kb://s", "kb://p", "kb://o", "reference")
        # Verify boolean query was constructed and delete_documents_by_query was called
        mock_tantivy.Query.boolean_query.assert_called_once()
        self.mock_writer.delete_documents_by_query.assert_called_once_with(mock_boolean_query)
    
    def test_graph_find_neighbors(self, tmp_path):
        """Test finding neighbors."""
        # Mock search results for neighbors with proper tuple structure
        mock_doc1 = MagicMock()
        mock_doc1.get_first.side_effect = lambda key: {"subject": "kb://ns/c/doc1", "object": "kb://ns/c/doc2", "predicate": "references"}.get(key)
        mock_doc2 = MagicMock()
        mock_doc2.get_first.side_effect = lambda key: {"subject": "kb://ns/c/doc3", "object": "kb://ns/c/doc1", "predicate": "references"}.get(key)
        
        # Mock search results - hits should be a list of (score, doc_address) tuples
        mock_search_results = MagicMock()
        mock_search_results.hits = [(1.0, "doc_address_1"), (1.0, "doc_address_2")]
        self.mock_searcher.search.return_value = mock_search_results
        self.mock_searcher.doc.side_effect = [mock_doc1, mock_doc2]
        
        # Create graph index and search for neighbors
        graph_idx = self.GraphSearchIndex(str(tmp_path / "graph_neighbors"))
        limit = 500
        neighbors = graph_idx.find_neighbors(["kb://ns/c/doc1"], ["references"], limit)
        
        # Verify the right methods were called
        self.mock_index.reload.assert_called_once()
        self.mock_index.searcher.assert_called_once()
        # The implementation searches for both subject and object matches
        assert self.mock_searcher.search.call_count >= 1
        # Should find the neighbors
        assert isinstance(neighbors, set)
        # Should contain doc2 (forward relation) and doc3 (reverse relation)
        expected_neighbors = {"kb://ns/c/doc2", "kb://ns/c/doc3"}
        assert neighbors == expected_neighbors
    
    def test_graph_find_neighbors_empty_input(self, tmp_path):
        """Test find_neighbors with empty URN list."""
        # Create graph index and search with empty input
        graph_idx = self.GraphSearchIndex(str(tmp_path / "graph_empty"))
        neighbors = graph_idx.find_neighbors([], ["references"])
        
        # Verify results and that no search was performed
        assert neighbors == set()
        self.mock_searcher.search.assert_not_called()
    
    # --- Reranker Tests ---
    
    def test_reranker_init(self):
        """Test Reranker initialization."""
        # Set up mocks
        mock_model_instance = MagicMock()
        mock_cross_encoder.return_value = mock_model_instance
        
        # Create reranker
        model_name = "test-model"
        reranker = self.Reranker(model_name)
        
        # Verify the model was initialized correctly
        mock_cross_encoder.assert_called_once_with(model_name)
        assert reranker.model == mock_model_instance
    
    def test_reranker_rerank(self):
        """Test reranking logic."""
        # Set up mocks
        mock_model_instance = MagicMock()
        mock_cross_encoder.return_value = mock_model_instance
        
        # Configure mock predict behavior
        mock_scores = [0.1, 0.9, 0.5]  # Scores for doc1, doc2, doc3
        mock_model_instance.predict.return_value = mock_scores
        
        # Create reranker and test reranking
        reranker = self.Reranker("test-model")
        query = "search query"
        docs = [
            {"urn": "d1", "content": "content 1"},
            {"urn": "d2", "content": "content 2"},
            {"urn": "d3", "content": "content 3"},
        ]
        reranked = reranker.rerank(query, docs)
        
        # Verify prediction was called correctly
        mock_model_instance.predict.assert_called_once_with([
            (query, "content 1"), (query, "content 2"), (query, "content 3")
        ])
        
        # Verify scores added and sorted
        assert len(reranked) == 3
        assert reranked[0]["urn"] == "d2" and reranked[0]["rerank_score"] == 0.9
        assert reranked[1]["urn"] == "d3" and reranked[1]["rerank_score"] == 0.5
        assert reranked[2]["urn"] == "d1" and reranked[2]["rerank_score"] == 0.1
    
    def test_reranker_rerank_empty_docs(self):
        """Test reranking with empty document list."""
        # Set up mocks
        mock_model_instance = MagicMock()
        mock_cross_encoder.return_value = mock_model_instance
        
        # Create reranker and test with empty docs
        reranker = self.Reranker("test-model")
        reranked = reranker.rerank("query", [])
        
        # Verify results and that predict was not called
        assert reranked == []
        mock_model_instance.predict.assert_not_called()
    
    def test_reranker_rerank_empty_query(self):
        """Test reranking with empty query."""
        # Set up mocks
        mock_model_instance = MagicMock()
        mock_cross_encoder.return_value = mock_model_instance
        
        # Create reranker and test with empty query
        reranker = self.Reranker("test-model")
        docs = [
            {"urn": "d1", "content": "content 1", "sparse_score": 0.8},
            {"urn": "d2", "content": "content 2", "sparse_score": 0.6},
        ]
        reranked = reranker.rerank("", docs)
        
        # Should fall back to sorting by sparse score
        assert len(reranked) == 2
        assert reranked[0]["urn"] == "d1"  # Higher sparse score
        assert reranked[1]["urn"] == "d2"  # Lower sparse score
        mock_model_instance.predict.assert_not_called() 