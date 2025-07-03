"""Tests for SparseSearchIndex module."""

import pytest
import sys
from unittest.mock import Mock, patch, MagicMock


class TestSparseSearchIndex:
    """Test suite for SparseSearchIndex."""
    
    def test_import_from_new_location(self):
        """RED: Test that we can import SparseSearchIndex from new location."""
        # This will fail initially
        from cmcp.kb.search.sparse import SparseSearchIndex
        assert SparseSearchIndex is not None
    
    def test_search_functionality(self):
        """RED: Test basic search functionality."""
        mock_tantivy = MagicMock()
        mock_schema = MagicMock()
        mock_schema_builder = MagicMock()
        mock_schema_builder.add_text_field = MagicMock()
        mock_schema_builder.build.return_value = mock_schema
        mock_tantivy.SchemaBuilder.return_value = mock_schema_builder
        mock_tantivy.Index.return_value = MagicMock()
        
        with patch.dict('sys.modules', {'tantivy': mock_tantivy}):
            from cmcp.kb.search.sparse import SparseSearchIndex
            index = SparseSearchIndex("/tmp/test_sparse")
            # Test will fail until implementation exists
            result = index.search("test query", top_k=5)
            assert isinstance(result, list)
    
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
    
    def test_initialization(self, mock_tantivy):
        """RED: Test SparseSearchIndex initialization."""
        from cmcp.kb.search.sparse import SparseSearchIndex
        
        index = SparseSearchIndex("/tmp/test")
        assert index.index_path.name == "test"
        mock_tantivy.SchemaBuilder.assert_called()
    
    def test_search_with_results(self, mock_tantivy):
        """RED: Test search returns expected format."""
        from cmcp.kb.search.sparse import SparseSearchIndex
        
        # Mock search results
        mock_searcher = Mock()
        mock_results = Mock()
        mock_results.hits = [(0.9, "doc1"), (0.8, "doc2")]
        mock_searcher.search.return_value = mock_results
        mock_searcher.doc.side_effect = [
            Mock(get_first=Mock(return_value="urn:doc1")),
            Mock(get_first=Mock(return_value="urn:doc2"))
        ]
        
        index = SparseSearchIndex("/tmp/test")
        index.index = Mock()
        index.index.searcher.return_value = mock_searcher
        
        results = index.search("test query", top_k=10)
        
        assert len(results) == 2
        assert results[0] == ("urn:doc1", 0.9)
        assert results[1] == ("urn:doc2", 0.8)
    
    def test_add_document(self, mock_tantivy):
        """RED: Test document addition."""
        from cmcp.kb.search.sparse import SparseSearchIndex
        
        index = SparseSearchIndex("/tmp/test")
        writer_mock = Mock()
        
        index.add_document(writer_mock, "urn:test", "content")
        
        # Verify document was created and added
        mock_tantivy.Document.assert_called()
        writer_mock.add_document.assert_called() 