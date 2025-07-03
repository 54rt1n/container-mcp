"""Tests for GraphSearchIndex module."""

import pytest
import sys
from unittest.mock import Mock, patch, MagicMock


class TestGraphSearchIndex:
    """Test suite for GraphSearchIndex."""
    
    def test_import_from_new_location(self):
        """RED: Test that we can import GraphSearchIndex from new location."""
        # This will fail initially
        from cmcp.kb.search.graph import GraphSearchIndex
        assert GraphSearchIndex is not None
    
    def test_find_neighbors_functionality(self):
        """RED: Test basic find_neighbors functionality."""
        mock_tantivy = MagicMock()
        mock_schema = MagicMock()
        mock_schema_builder = MagicMock()
        mock_schema_builder.add_text_field = MagicMock()
        mock_schema_builder.build.return_value = mock_schema
        mock_tantivy.SchemaBuilder.return_value = mock_schema_builder
        mock_tantivy.Index.return_value = MagicMock()
        
        with patch.dict('sys.modules', {'tantivy': mock_tantivy}):
            from cmcp.kb.search.graph import GraphSearchIndex
            index = GraphSearchIndex("/tmp/test_graph")
            # Test will fail until implementation exists
            result = index.find_neighbors(["test:urn"])
            assert isinstance(result, set)
    
    @pytest.fixture
    def mock_tantivy(self):
        """Mock tantivy module."""
        mock_tantivy = MagicMock()
        
        # Set up mock schema builder
        mock_schema = MagicMock()
        mock_schema_builder = MagicMock()
        mock_schema_builder.add_text_field = MagicMock()
        mock_schema_builder.build.return_value = mock_schema
        mock_tantivy.SchemaBuilder.return_value = mock_schema_builder
        
        # Set up mock index
        mock_index = MagicMock()
        mock_tantivy.Index.return_value = mock_index
        
        with patch.dict('sys.modules', {'tantivy': mock_tantivy}):
            yield mock_tantivy
    
    def test_add_triple_functionality(self, mock_tantivy):
        """RED: Test triple addition."""
        from cmcp.kb.search.graph import GraphSearchIndex
        
        index = GraphSearchIndex("/tmp/test")
        writer_mock = Mock()
        
        index.add_triple(writer_mock, "subject:urn", "predicate", "object:urn", "reference")
        
        # Verify document was created and added
        mock_tantivy.Document.assert_called()
        writer_mock.add_document.assert_called()
    
    def test_find_neighbors_with_relations(self, mock_tantivy):
        """RED: Test find_neighbors with relation predicates."""
        from cmcp.kb.search.graph import GraphSearchIndex
        
        # Mock search results
        mock_searcher = Mock()
        mock_results = Mock()
        mock_results.hits = [(0.9, "doc1"), (0.8, "doc2")]
        mock_searcher.search.return_value = mock_results
        
        # Create mock documents with proper field values
        mock_doc1 = Mock()
        mock_doc1.get_first.side_effect = lambda field: {
            "subject": "subject:urn",
            "predicate": "predicate",
            "object": "object:urn1",
            "triple_type": "reference"
        }[field]
        
        mock_doc2 = Mock()
        mock_doc2.get_first.side_effect = lambda field: {
            "subject": "subject:urn",
            "predicate": "predicate",
            "object": "object:urn2",
            "triple_type": "reference"
        }[field]
        
        mock_searcher.doc.side_effect = [mock_doc1, mock_doc2]
        
        index = GraphSearchIndex("/tmp/test")
        index.index = Mock()
        index.index.searcher.return_value = mock_searcher
        
        results = index.find_neighbors(["subject:urn"], ["predicate"], 10)
        
        assert isinstance(results, set)
        assert "object:urn1" in results
        assert "object:urn2" in results 