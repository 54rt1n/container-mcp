"""Tests for SearchService module."""

import pytest
from unittest.mock import Mock, AsyncMock, patch


class TestSearchService:
    """Test suite for SearchService."""
    
    def test_import_from_new_location(self):
        """RED: Test that we can import SearchService from new location."""
        from cmcp.kb.search.service import SearchService
        assert SearchService is not None
    
    def test_initialization(self):
        """RED: Test SearchService initialization."""
        from cmcp.kb.search.service import SearchService
        
        manager_mock = Mock()
        recovery_mock = Mock()
        document_store_mock = Mock()
        
        service = SearchService(manager_mock, recovery_mock, document_store_mock, [], 100)
        assert service.search_index_manager == manager_mock
        assert service.search_recovery == recovery_mock
        assert service.document_store == document_store_mock
    
    @pytest.mark.asyncio
    async def test_search_async(self):
        """RED: Test async search functionality."""
        from cmcp.kb.search.service import SearchService
        
        manager_mock = Mock()
        manager_mock.search_sparse.return_value = [] # Ensure it returns an iterable
        service = SearchService(manager_mock, Mock(), Mock(), [], 100)
        
        # This should be extracted from KBM.search()
        result = await service.search(query="test", top_k_rerank=5)
        assert isinstance(result, list)
    
    @pytest.fixture
    def service_with_mocks(self):
        """Create service with mocked dependencies."""
        manager_mock = Mock()
        recovery_mock = Mock()
        document_store_mock = Mock()
        
        from cmcp.kb.search.service import SearchService
        return SearchService(manager_mock, recovery_mock, document_store_mock, [], 100)
    
    @pytest.mark.asyncio
    async def test_search_orchestration(self, service_with_mocks):
        """RED: Test async search orchestration extracted from KBM."""
        service = service_with_mocks
        
        # Mock the extracted methods
        service._get_candidate_urns = AsyncMock(return_value=({"urn:doc1", "urn:doc2"}, {"urn:doc1": 0.9}))
        service._fetch_content_for_candidates = AsyncMock(return_value=(
            [{"urn": "urn:doc1", "content": "content1"}], 
            [{"urn": "urn:doc2", "error": "no content"}]
        ))
        service._prepare_final_results = AsyncMock(return_value=[
            {"urn": "urn:doc1", "rerank_score": 0.95}
        ])
        
        result = await service.search(query="test", top_k_rerank=10)
        
        # Verify orchestration flow from KBM.search()
        service._get_candidate_urns.assert_called_once()
        service._fetch_content_for_candidates.assert_called_once()
        service._prepare_final_results.assert_called_once()
        
        assert len(result) == 1
        assert result[0]["urn"] == "urn:doc1"
    
    @pytest.mark.asyncio  
    async def test_update_document_in_indices(self, service_with_mocks):
        """RED: Test document index update coordination."""
        service = service_with_mocks
        
        # Mock async operation using to_thread
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = AsyncMock()
            
            await service.update_document_in_indices("urn:test", "content")
            
            # Should delegate to manager via asyncio.to_thread
            mock_to_thread.assert_called() 