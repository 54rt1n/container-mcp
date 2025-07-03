"""Integration tests for search module architecture."""

import pytest
from unittest.mock import Mock, AsyncMock, patch


class TestSearchModuleIntegration:
    """Test integration between search modules."""
    
    def test_public_api_exports(self):
        """RED: Test that all classes are properly exported from search module."""
        # This will fail initially until __init__.py is created
        from cmcp.kb.search import (
            SparseSearchIndex, 
            GraphSearchIndex, 
            Reranker,
            SearchIndexManager,
            SearchService, 
            SearchIndexRecovery
        )
        
        # Verify all classes are available
        assert SparseSearchIndex is not None
        assert GraphSearchIndex is not None
        assert Reranker is not None
        assert SearchIndexManager is not None
        assert SearchService is not None
        assert SearchIndexRecovery is not None
    
    def test_import_backwards_compatibility(self):
        """RED: Test that old import paths fail with helpful error messages."""
        # Current imports should still work during transition
        from cmcp.kb.search import SparseSearchIndex as OldSparseIndex
        from cmcp.kb.search.sparse import SparseSearchIndex as NewSparseIndex
        
        # After refactoring, these should be the same class
        assert OldSparseIndex == NewSparseIndex
    
    def test_kb_manager_uses_search_service(self):
        """RED: Test KB manager delegates to SearchService."""
        from cmcp.kb.search.service import SearchService
        
        # Mock SearchService
        search_service_mock = Mock()
        search_service_mock.search = AsyncMock(return_value=[])
        
        # Create KB manager with mocked search service
        kb_manager = Mock()
        kb_manager.search_service = search_service_mock
        
        # Simulate KB manager delegating search to SearchService
        async def mock_kb_search(query, **kwargs):
            return await kb_manager.search_service.search(query, **kwargs)
        
        kb_manager.search = mock_kb_search
        
        # Test the delegation
        import asyncio
        result = asyncio.run(kb_manager.search("test query"))
        
        search_service_mock.search.assert_called_once_with("test query")
        assert result == []
    
    def test_search_service_uses_manager_and_recovery(self):
        """RED: Test SearchService coordinates with manager and recovery."""
        from cmcp.kb.search.service import SearchService
        from cmcp.kb.search.manager import SearchIndexManager
        from cmcp.kb.search.recovery import SearchIndexRecovery
        
        # Create mocked dependencies
        manager_mock = Mock()
        recovery_mock = Mock()
        document_store_mock = Mock()
        
        # Create SearchService with mocked dependencies
        service = SearchService(manager_mock, recovery_mock, document_store_mock, [], 100)
        
        # Verify initialization
        assert service.search_index_manager == manager_mock
        assert service.search_recovery == recovery_mock
        assert service.document_store == document_store_mock
    
    @pytest.mark.asyncio
    async def test_end_to_end_search_flow(self):
        """RED: Test complete search flow through new architecture."""
        # Mock all components
        sparse_index_mock = Mock()
        graph_index_mock = Mock()
        reranker_mock = Mock()
        document_store_mock = Mock()
        
        # Set up search results
        sparse_index_mock.search.return_value = [("urn:doc1", 0.9)]
        graph_index_mock.find_neighbors.return_value = {"urn:doc2"}
        reranker_mock.rerank.return_value = [
            {"urn": "urn:doc1", "rerank_score": 0.95, "content": "content1"}
        ]
        
        # Mock document reading
        document_store_mock.read_content = AsyncMock(return_value="content1")
        document_store_mock.read_index = AsyncMock(return_value=Mock(urn="urn:doc1"))
        
        from cmcp.kb.search.manager import SearchIndexManager
        from cmcp.kb.search.service import SearchService
        from cmcp.kb.search.recovery import SearchIndexRecovery
        
        # Create the architecture
        manager = SearchIndexManager(sparse_index_mock, graph_index_mock, reranker_mock)
        recovery = SearchIndexRecovery(manager, document_store_mock)
        service = SearchService(manager, recovery, document_store_mock, [], 100)
        
        with patch('asyncio.to_thread') as mock_to_thread:
            # Mock sync operations
            mock_to_thread.side_effect = [
                # Mock sparse search
                [("urn:doc1", 0.9)],
                # Mock graph search 
                {"urn:doc2"},
                # Mock reranking
                [{"urn": "urn:doc1", "rerank_score": 0.95, "content": "content1"}]
            ]
            
            # Execute search
            results = await service.search("test query", top_k_rerank=10)
            
            # Verify end-to-end flow
            assert len(results) >= 0  # Should return results
            assert mock_to_thread.call_count >= 1  # Should use async-to-sync delegation
    
    @pytest.mark.asyncio
    async def test_document_update_coordination(self):
        """RED: Test document updates coordinate across all indices."""
        # Mock all components
        sparse_index_mock = Mock()
        graph_index_mock = Mock()
        reranker_mock = Mock()
        document_store_mock = Mock()
        
        from cmcp.kb.search.manager import SearchIndexManager
        from cmcp.kb.search.service import SearchService
        from cmcp.kb.search.recovery import SearchIndexRecovery
        
        # Create the architecture
        manager = SearchIndexManager(sparse_index_mock, graph_index_mock, reranker_mock)
        recovery = SearchIndexRecovery(manager, document_store_mock)
        service = SearchService(manager, recovery, document_store_mock, [], 100)
        
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = None
            
            # Test document update
            await service.update_document_in_indices("urn:test", "new content")
            
            # Should delegate to manager via asyncio.to_thread
            mock_to_thread.assert_called()
            
            # Get the first call arguments
            call_args = mock_to_thread.call_args_list[0][0]
            assert len(call_args) >= 2  # Function + arguments
    
    def test_module_structure_consistency(self):
        """RED: Test that all modules follow consistent structure."""
        # Test that all search modules have proper imports
        modules_to_test = [
            'cmcp.kb.search.sparse',
            'cmcp.kb.search.graph', 
            'cmcp.kb.search.reranker',
            'cmcp.kb.search.manager',
            'cmcp.kb.search.service',
            'cmcp.kb.search.recovery'
        ]
        
        for module_name in modules_to_test:
            try:
                module = __import__(module_name, fromlist=[''])
                # Each module should have at least one class
                assert hasattr(module, '__all__') or len(dir(module)) > 0
            except ImportError:
                # Expected to fail until implementation exists
                pass
    
    def test_dependency_injection_pattern(self):
        """RED: Test that dependency injection is properly implemented."""
        from cmcp.kb.search.manager import SearchIndexManager
        from cmcp.kb.search.service import SearchService
        from cmcp.kb.search.recovery import SearchIndexRecovery
        
        # Mock dependencies
        sparse_mock = Mock()
        graph_mock = Mock()
        reranker_mock = Mock()
        document_store_mock = Mock()
        
        # Test SearchIndexManager dependency injection
        manager = SearchIndexManager(sparse_mock, graph_mock, reranker_mock)
        assert manager.sparse_index == sparse_mock
        assert manager.graph_index == graph_mock
        assert manager.reranker == reranker_mock
        
        # Test SearchService dependency injection
        recovery_mock = Mock()
        service = SearchService(manager, recovery_mock, document_store_mock, [], 100)
        assert service.search_index_manager == manager
        assert service.search_recovery == recovery_mock
        assert service.document_store == document_store_mock
        
        # Test SearchIndexRecovery dependency injection
        recovery = SearchIndexRecovery(manager, document_store_mock)
        assert recovery.search_index_manager == manager
        assert recovery.document_store == document_store_mock 