"""Public API for the Knowledge Base Search module.

This file exports all the major classes from the new search submodules,
providing a single, consistent entry point for other parts of the application
to use the search functionality. This aligns with the public API testing
in test_integration.py and provides backward compatibility for imports.
"""

from .sparse import SparseSearchIndex
from .graph import GraphSearchIndex
from .reranker import Reranker
from .manager import SearchIndexManager
from .service import SearchService
from .recovery import SearchIndexRecovery

__all__ = [
    "SparseSearchIndex",
    "GraphSearchIndex",
    "Reranker",
    "SearchIndexManager",
    "SearchService",
    "SearchIndexRecovery",
] 