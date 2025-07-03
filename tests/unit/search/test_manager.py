"""Tests for SearchIndexManager module."""

import pytest
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture
def manager_with_mocks():
    """Fixture to create a SearchIndexManager with mocked dependencies."""
    from cmcp.kb.search.manager import SearchIndexManager
    
    sparse_mock = MagicMock()
    graph_mock = MagicMock()
    reranker_mock = MagicMock()

    # Configure the get_writer mocks to support the context manager protocol
    # Assign the return_value to a variable to configure it correctly
    sparse_writer_cm = sparse_mock.get_writer.return_value
    sparse_writer_cm.__enter__.return_value = MagicMock()  # This mock is the 'writer'
    sparse_writer_cm.__exit__.return_value = None

    graph_writer_cm = graph_mock.get_writer.return_value
    graph_writer_cm.__enter__.return_value = MagicMock()
    graph_writer_cm.__exit__.return_value = None

    manager = SearchIndexManager(sparse_mock, graph_mock, reranker_mock)
    return manager, sparse_mock, graph_mock, reranker_mock

class TestSearchIndexManager:
    """Test suite for SearchIndexManager."""
    
    def test_import_from_new_location(self):
        """GREEN: Test that we can import SearchIndexManager from new location."""
        from cmcp.kb.search.manager import SearchIndexManager
        assert SearchIndexManager is not None
    
    def test_initialization(self):
        """GREEN: Test SearchIndexManager initialization."""
        from cmcp.kb.search.manager import SearchIndexManager
        
        sparse_mock = MagicMock()
        graph_mock = MagicMock()  
        reranker_mock = MagicMock()
        
        manager = SearchIndexManager(sparse_mock, graph_mock, reranker_mock)
        assert manager.sparse_index == sparse_mock
        assert manager.graph_index == graph_mock
        assert manager.reranker == reranker_mock
    
    def test_update_sparse_index(self):
        """GREEN: Test sync sparse index update."""
        from cmcp.kb.search.manager import SearchIndexManager
        
        sparse_mock = MagicMock()
        # Correctly mock the context manager
        writer_cm = sparse_mock.get_writer.return_value
        writer_mock = MagicMock()
        writer_cm.__enter__.return_value = writer_mock
        writer_cm.__exit__.return_value = None

        manager = SearchIndexManager(sparse_mock, MagicMock(), MagicMock())
        
        manager.update_sparse_index("urn:test", "content")
    
        # Assert that get_writer was called, and methods were called on the index mock
        sparse_mock.get_writer.assert_called_once()
        sparse_mock.delete_document.assert_called_once_with(writer_mock, "urn:test")
        sparse_mock.add_document.assert_called_once_with(writer_mock, "urn:test", "content")
    
    def test_update_sparse_index_calls_correct_methods(self, manager_with_mocks):
        """GREEN: Test that update_sparse_index calls the correct underlying methods."""
        manager, sparse_mock, _, _ = manager_with_mocks
        
        manager.update_sparse_index("urn:test", "content")

        sparse_mock.get_writer.assert_called_once()
        writer_mock = sparse_mock.get_writer.return_value.__enter__.return_value
        sparse_mock.delete_document.assert_called_once_with(writer_mock, "urn:test")
        sparse_mock.add_document.assert_called_once_with(writer_mock, "urn:test", "content")
    
    def test_add_triple_calls_correct_methods(self, manager_with_mocks):
        """GREEN: Test that add_triple calls the correct underlying methods."""
        manager, _, graph_mock, _ = manager_with_mocks
        
        manager.add_triple("s", "p", "o", "t")

        graph_mock.get_writer.assert_called_once()
        writer_mock = graph_mock.get_writer.return_value.__enter__.return_value
        graph_mock.add_triple.assert_called_once_with(writer_mock, "s", "p", "o", "t")
    
    def test_search_sparse_delegates_correctly(self, manager_with_mocks):
        """GREEN: Test sparse search delegation."""
        manager, sparse_mock, _, _ = manager_with_mocks
        sparse_mock.search.return_value = [("urn:doc", 0.9)]
        
        result = manager.search_sparse("query", 10, 0, None)
        
        sparse_mock.search.assert_called_with("query", 10, 0, None)
        assert result == [("urn:doc", 0.9)]
    
    def test_delete_sparse_index(self, manager_with_mocks):
        """GREEN: Test that delete_sparse_index calls the correct methods."""
        manager, sparse_mock, _, _ = manager_with_mocks
        manager.delete_sparse_index("urn:to_delete")
        sparse_mock.get_writer.assert_called_once()
        writer_mock = sparse_mock.get_writer.return_value.__enter__.return_value
        sparse_mock.delete_document.assert_called_once_with(writer_mock, "urn:to_delete")
    
    def test_delete_triple(self, manager_with_mocks):
        """GREEN: Test that delete_triple calls the correct methods."""
        manager, _, graph_mock, _ = manager_with_mocks
        manager.delete_triple("s", "p", "o", "t")
        graph_mock.get_writer.assert_called_once()
        writer_mock = graph_mock.get_writer.return_value.__enter__.return_value
        graph_mock.delete_triple.assert_called_once_with(writer_mock, "s", "p", "o", "t")
    
    def test_delete_document_from_graph(self, manager_with_mocks):
        """GREEN: Test that delete_document_from_graph calls the correct methods."""
        manager, _, graph_mock, _ = manager_with_mocks
        manager.delete_document_from_graph("urn:to_delete")
        graph_mock.get_writer.assert_called_once()
        writer_mock = graph_mock.get_writer.return_value.__enter__.return_value
        graph_mock.delete_document.assert_called_once_with(writer_mock, "urn:to_delete")
    
    def test_find_neighbors_calls_correct_methods(self, manager_with_mocks):
        """GREEN: Test neighbor finding extracted from KBM."""
        manager, _, graph_mock, _ = manager_with_mocks
        graph_mock.find_neighbors.return_value = {"urn:neighbor1", "urn:neighbor2"}
        
        result = manager.find_neighbors(["urn:start"], ["references"], 1000, None)
        
        graph_mock.find_neighbors.assert_called_with(["urn:start"], ["references"], 1000, None)
        assert result == {"urn:neighbor1", "urn:neighbor2"}
    
    def test_rerank_docs_calls_correct_methods(self, manager_with_mocks):
        """GREEN: Test document reranking extracted from KBM."""
        manager, _, _, reranker_mock = manager_with_mocks
        docs = [{"urn": "a", "content": "b"}]
        reranked_docs = [{"urn": "a", "content": "b", "rerank_score": 0.9}]
        reranker_mock.rerank.return_value = reranked_docs
        
        result = manager.rerank_docs("query", docs)
        
        reranker_mock.rerank.assert_called_with("query", docs)
        assert result == reranked_docs
    
    def test_update_moved_document_sparse(self, manager_with_mocks):
        """GREEN: Test update_moved_document_sparse calls correct methods."""
        manager, sparse_mock, _, _ = manager_with_mocks
        manager.update_moved_document_sparse("old_urn", "new_urn", "content")
        sparse_mock.get_writer.assert_called_once()
        writer_mock = sparse_mock.get_writer.return_value.__enter__.return_value
        sparse_mock.delete_document.assert_called_once_with(writer_mock, "old_urn")
        sparse_mock.add_document.assert_called_once_with(writer_mock, "new_urn", "content")
    
    def test_update_moved_document_graph(self, manager_with_mocks):
        """GREEN: Test graph index update for moved documents."""
        manager, _, graph_mock, _ = manager_with_mocks
        
        manager.update_moved_document_graph("old_urn", "new_urn")
    
        graph_mock.update_moved_document.assert_called_once_with("old_urn", "new_urn")
    
    def test_update_sparse_index_failure(self, manager_with_mocks):
        """GREEN: Test that sparse index update failure rolls back changes."""
        manager, sparse_mock, _, _ = manager_with_mocks
        sparse_mock.add_document.side_effect = ValueError("Index write failed")

        with pytest.raises(ValueError):
            manager.update_sparse_index("urn:fail", "content")

        # Check that the context manager was exited with an exception
        exit_mock = sparse_mock.get_writer.return_value.__exit__
        exit_mock.assert_called_once()
        assert exit_mock.call_args[0][0] is ValueError
    
    def test_add_triple_failure(self, manager_with_mocks):
        """GREEN: Test that graph index update failure rolls back changes."""
        manager, _, graph_mock, _ = manager_with_mocks
        graph_mock.add_triple.side_effect = ValueError("Index write failed")

        with pytest.raises(ValueError):
            manager.add_triple("s", "p", "o", "t")

        # Check that the context manager was exited with an exception
        exit_mock = graph_mock.get_writer.return_value.__exit__
        exit_mock.assert_called_once()
        assert exit_mock.call_args[0][0] is ValueError 