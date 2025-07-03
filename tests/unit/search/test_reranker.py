"""Tests for Reranker module."""

import pytest
import sys
from unittest.mock import Mock, patch, MagicMock


class TestReranker:
    """Test suite for Reranker."""
    
    def test_import_from_new_location(self):
        """RED: Test that we can import Reranker from new location.""" 
        from cmcp.kb.search.reranker import Reranker
        assert Reranker is not None
    
    def test_rerank_functionality(self):
        """RED: Test basic reranking functionality."""
        # Create mock CrossEncoder
        mock_cross_encoder_class = MagicMock()
        mock_cross_encoder_instance = MagicMock()
        mock_cross_encoder_instance.predict.return_value = [0.5]
        mock_cross_encoder_class.return_value = mock_cross_encoder_instance
        
        # Mock the sentence_transformers module
        mock_st_ce = MagicMock(CrossEncoder=mock_cross_encoder_class)
        
        with patch.dict('sys.modules', {'sentence_transformers.cross_encoder': mock_st_ce}):
            from cmcp.kb.search.reranker import Reranker
            reranker = Reranker("test-model")
            docs = [{"urn": "test", "content": "test content"}]
            result = reranker.rerank("query", docs)
            assert isinstance(result, list)
            assert "rerank_score" in result[0]
    
    def test_rerank_with_scores(self):
        """RED: Test reranking adds scores correctly."""
        # Create mock CrossEncoder
        mock_cross_encoder_class = MagicMock()
        mock_cross_encoder_instance = MagicMock()
        mock_cross_encoder_instance.predict.return_value = [0.9, 0.7, 0.8]
        mock_cross_encoder_class.return_value = mock_cross_encoder_instance
        
        # Mock the sentence_transformers module
        mock_st_ce = MagicMock(CrossEncoder=mock_cross_encoder_class)
        
        with patch.dict('sys.modules', {'sentence_transformers.cross_encoder': mock_st_ce}):
            from cmcp.kb.search.reranker import Reranker
            reranker = Reranker("test-model")
            
            docs = [
                {"urn": "doc1", "content": "relevant"},
                {"urn": "doc2", "content": "less relevant"},  
                {"urn": "doc3", "content": "somewhat relevant"}
            ]
            
            result = reranker.rerank("test query", docs)
            
            # Should be sorted by rerank_score (descending)
            assert result[0]["urn"] == "doc1"  # highest score 0.9
            assert result[1]["urn"] == "doc3"  # middle score 0.8
            assert result[2]["urn"] == "doc2"  # lowest score 0.7
            
            assert result[0]["rerank_score"] == 0.9
            assert result[1]["rerank_score"] == 0.8
            assert result[2]["rerank_score"] == 0.7 