"""Tests for SearchIndexRecovery module."""

import pytest
from unittest.mock import Mock, AsyncMock, patch


class TestSearchIndexRecovery:
    """Test suite for SearchIndexRecovery."""
    
    def test_import_from_new_location(self):
        """RED: Test that we can import SearchIndexRecovery from new location."""
        from cmcp.kb.search.recovery import SearchIndexRecovery
        assert SearchIndexRecovery is not None
    
    def test_initialization(self):
        """RED: Test SearchIndexRecovery initialization."""
        from cmcp.kb.search.recovery import SearchIndexRecovery
        
        manager_mock = Mock()
        document_store_mock = Mock()
        
        recovery = SearchIndexRecovery(manager_mock, document_store_mock)
        assert recovery.search_index_manager == manager_mock
        assert recovery.document_store == document_store_mock
    
    @pytest.mark.asyncio
    async def test_recover_indices_async(self):
        """RED: Test async index recovery."""
        from cmcp.kb.search.recovery import SearchIndexRecovery
        
        doc_store_mock = AsyncMock()
        doc_store_mock.list_documents.return_value = []
        recovery = SearchIndexRecovery(Mock(), doc_store_mock)
        
        # This should be extracted from KBM.recover_search_indices()
        result = await recovery.recover_indices(rebuild_all=True)
        assert isinstance(result, dict)
    
    @pytest.fixture
    def recovery_with_mocks(self):
        """Create recovery with mocked dependencies."""
        manager_mock = Mock()
        document_store_mock = Mock()
        
        from cmcp.kb.search.recovery import SearchIndexRecovery
        return SearchIndexRecovery(manager_mock, document_store_mock)
    
    @pytest.mark.asyncio
    async def test_recover_indices_orchestration(self, recovery_with_mocks):
        """RED: Test recovery orchestration extracted from KBM."""
        recovery = recovery_with_mocks
        
        # Mock the extracted methods
        with patch.object(recovery, '_clear_indices_for_rebuild', new_callable=AsyncMock) as clear_mock, \
             patch.object(recovery, '_rebuild_indices_from_documents', new_callable=AsyncMock) as rebuild_mock:
            
            result = await recovery.recover_indices(rebuild_all=True)
            
            # Verify recovery flow from KBM.recover_search_indices()
            clear_mock.assert_called_once()
            rebuild_mock.assert_called_once()
            
            assert result["sparse_index"]["status"] == "rebuilt"
            assert result["graph_index"]["status"] == "rebuilt"
    
    @pytest.mark.asyncio
    async def test_rebuild_from_documents(self, recovery_with_mocks):
        """RED: Test document rebuild process."""
        recovery = recovery_with_mocks
        
        # Mock document store to return test documents
        recovery.document_store.find_documents_recursive = AsyncMock(return_value=[
            "docs/general/test1", "docs/general/test2"
        ])
        recovery.document_store.list_documents = AsyncMock(return_value=[
            "docs/general/test1", "docs/general/test2"
        ])
        recovery.document_store.read_index = AsyncMock(return_value=Mock(references=[], preferences=[]))
        recovery.document_store.read_content = AsyncMock(return_value="some content")
        
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = AsyncMock()
            
            status = {"documents_processed": 0, "triples_processed": 0}
            await recovery._rebuild_indices_from_documents(status)
            
            assert status["documents_processed"] == 2
            # Should call manager methods via asyncio.to_thread
            assert mock_to_thread.call_count > 0
    
    @pytest.mark.asyncio
    async def test_clear_indices_for_rebuild(self, recovery_with_mocks):
        """RED: Test index clearing extracted from KBM._clear_indices_for_rebuild."""
        recovery = recovery_with_mocks
        
        # Mock the extracted methods
        recovery.search_index_manager.sparse_index.clear_index = Mock()
        recovery.search_index_manager.graph_index.clear_index = Mock()
        
        status = {"sparse_cleared": False, "graph_cleared": False}
        await recovery.clear_indices(status)
        
        # Verify clearing flow from KBM._clear_indices_for_rebuild
        recovery.search_index_manager.sparse_index.clear_index.assert_called_once()
        recovery.search_index_manager.graph_index.clear_index.assert_called_once()
        
        assert status["sparse_cleared"] is True
        assert status["graph_cleared"] is True
    
    @pytest.mark.asyncio
    async def test_rebuild_indices_from_documents(self, recovery_with_mocks):
        """RED: Test document rebuilding extracted from KBM._rebuild_indices_from_documents."""
        recovery = recovery_with_mocks
        
        # Mock document store methods
        recovery.document_store.find_documents_recursive = AsyncMock(return_value=[
            "ns/coll/doc1", "ns/coll/doc2"
        ])
        recovery.document_store.list_documents = AsyncMock(return_value=[
            "ns/coll/doc1", "ns/coll/doc2"
        ])
        
        # Mock read operations for content and index
        async def mock_read_content(components):
            return f"Content for {components.path}"
        
        async def mock_read_index(components):
            mock_index = Mock()
            mock_index.references = []
            mock_index.preferences = []
            mock_index.uri = f"kb://{components.path}"
            return mock_index
        
        recovery.document_store.read_content = AsyncMock(side_effect=mock_read_content)
        recovery.document_store.read_index = AsyncMock(side_effect=mock_read_index)
        
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = AsyncMock()
            
            status = {"documents_processed": 0, "triples_processed": 0}
            await recovery.rebuild_indices_from_documents(status)
            
            # Verify document processing from KBM._rebuild_indices_from_documents
            assert status["documents_processed"] == 2
            # Should call manager update methods via asyncio.to_thread
            assert mock_to_thread.call_count >= 2  # At least one call per document
    
    @pytest.mark.asyncio
    async def test_recover_indices_with_errors(self, recovery_with_mocks):
        """RED: Test recovery error handling."""
        recovery = recovery_with_mocks
        
        # Mock methods to raise errors
        with patch.object(recovery, '_clear_indices_for_rebuild', new_callable=AsyncMock) as clear_mock:
            clear_mock.side_effect = Exception("Clear failed")
        
            with pytest.raises(Exception, match="Clear failed"):
                await recovery.recover_indices(rebuild_all=True)
    
    @pytest.mark.asyncio
    async def test_recover_indices_partial_rebuild(self, recovery_with_mocks):
        """RED: Test partial index recovery without full rebuild."""
        recovery = recovery_with_mocks
        
        # Mock sparse and graph index recovery methods
        recovery.search_index_manager.sparse_index._recover_index = Mock()
        recovery.search_index_manager.graph_index._recover_index = Mock()
        
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = AsyncMock()
            
            result = await recovery.recover_indices(rebuild_all=False)
            
            # Should attempt recovery without full rebuild
            assert mock_to_thread.call_count >= 2  # sparse + graph recovery
            assert result["sparse_index"]["status"] == "recovered"
            assert result["graph_index"]["status"] == "recovered" 