# tests/integration/test_knowledge_base.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Integration tests for the knowledge base system."""

import os
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone

from cmcp.managers import KnowledgeBaseManager
from cmcp.kb.path import PathComponents, PartialPathComponents
from cmcp.kb.models import DocumentIndex, ImplicitRDFTriple


@pytest.fixture
async def kb_manager():
    """Create a knowledge base manager with temporary storage for testing."""
    # Create a temporary directory for testing
    temp_dir = tempfile.mkdtemp()
    
    # Initialize knowledge base manager with temporary storage
    kbm = KnowledgeBaseManager(
        storage_path=temp_dir,
        timeout_default=30,
        timeout_max=300,
        search_enabled=False  # Disable search for integration tests
    )
    
    await kbm.initialize()
    
    yield kbm
    
    # Clean up temporary directory
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
async def kb_manager_with_search():
    """Create a knowledge base manager with search enabled for testing."""
    # Create a temporary directory for testing
    temp_dir = tempfile.mkdtemp()
    
    # Initialize knowledge base manager with temporary storage and search
    kbm = KnowledgeBaseManager(
        storage_path=temp_dir,
        timeout_default=30,
        timeout_max=300,
        search_enabled=True
    )
    
    await kbm.initialize()
    
    yield kbm
    
    # Clean up temporary directory
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_document_lifecycle(kb_manager):
    """Test the complete document lifecycle: create, write, read, update, delete."""
    # Test document creation
    path = PathComponents.parse_path('test/docs/sample')
    metadata = {'title': 'Test Document', 'author': 'Test User'}
    
    index = await kb_manager.create_document(path, metadata)
    assert index.namespace == 'test'
    assert index.collection == 'docs'
    assert index.name == 'sample'
    assert index.metadata['title'] == 'Test Document'
    assert index.metadata['author'] == 'Test User'
    
    # Test content writing
    content = 'Hello World! This is a test document with some content.'
    updated_index = await kb_manager.write_content(path, content)
    assert updated_index.updated_at >= index.updated_at  # Should be updated
    
    # Test content reading
    read_content = await kb_manager.read_content(path)
    assert read_content == content
    
    # Test index reading
    read_index = await kb_manager.read_index(path)
    assert read_index.namespace == 'test'
    assert read_index.collection == 'docs'
    assert read_index.name == 'sample'
    assert read_index.metadata['title'] == 'Test Document'
    
    # Test metadata update
    new_metadata = {'title': 'Updated Test Document', 'version': '2.0'}
    updated_index = await kb_manager.update_metadata(path, new_metadata)
    assert updated_index.metadata['title'] == 'Updated Test Document'
    assert updated_index.metadata['version'] == '2.0'
    assert updated_index.metadata['author'] == 'Test User'  # Should still be there
    
    # Test document deletion
    delete_result = await kb_manager.delete_document(path)
    assert delete_result['status'] == 'deleted'
    
    # Verify document is deleted
    with pytest.raises(FileNotFoundError):
        await kb_manager.read_index(path)


@pytest.mark.asyncio
async def test_document_preferences(kb_manager):
    """Test adding and removing preferences from documents."""
    # Create a document
    path = PathComponents.parse_path('test/prefs/document')
    await kb_manager.create_document(path, {'title': 'Preferences Test'})
    
    # Add preferences
    preferences = [
        ImplicitRDFTriple(predicate='likes', object='python'),
        ImplicitRDFTriple(predicate='uses', object='pytest'),
        ImplicitRDFTriple(predicate='prefers', object='async')
    ]
    
    result = await kb_manager.add_preference(path, preferences)
    assert result['status'] == 'updated'
    assert result['preference_count'] == 3
    
    # Verify preferences were added
    index = await kb_manager.read_index(path)
    assert len(index.preferences) == 3
    assert ImplicitRDFTriple(predicate='likes', object='python') in index.preferences
    
    # Remove specific preferences
    to_remove = [ImplicitRDFTriple(predicate='likes', object='python')]
    result = await kb_manager.remove_preference(path, to_remove)
    assert result['status'] == 'updated'
    assert result['preference_count'] == 2
    
    # Verify preference was removed
    index = await kb_manager.read_index(path)
    assert len(index.preferences) == 2
    assert ImplicitRDFTriple(predicate='likes', object='python') not in index.preferences
    assert ImplicitRDFTriple(predicate='uses', object='pytest') in index.preferences
    
    # Remove all preferences
    result = await kb_manager.remove_all_preferences(path)
    assert result['status'] == 'updated'
    assert result['preference_count'] == 0
    
    # Verify all preferences were removed
    index = await kb_manager.read_index(path)
    assert len(index.preferences) == 0


@pytest.mark.asyncio
async def test_document_references(kb_manager):
    """Test adding and removing references between documents."""
    # Create source and target documents
    source_path = PathComponents.parse_path('test/refs/source')
    target_path = PathComponents.parse_path('test/refs/target')
    
    await kb_manager.create_document(source_path, {'title': 'Source Document'})
    await kb_manager.create_document(target_path, {'title': 'Target Document'})
    
    # Add reference
    result = await kb_manager.add_reference(source_path, target_path, 'references')
    assert result['status'] == 'success'
    assert result['added'] is True
    
    # Verify reference was added
    index = await kb_manager.read_index(source_path)
    assert len(index.references) == 1
    assert ImplicitRDFTriple(predicate='references', object=target_path.uri) in index.references
    
    # Try adding the same reference again (should not duplicate)
    result = await kb_manager.add_reference(source_path, target_path, 'references')
    assert result['status'] == 'success'
    assert result['added'] is False  # Already existed
    
    # Verify still only one reference
    index = await kb_manager.read_index(source_path)
    assert len(index.references) == 1
    
    # Add another reference with different relation
    another_target = PathComponents.parse_path('test/refs/another')
    await kb_manager.create_document(another_target, {'title': 'Another Document'})
    
    await kb_manager.add_reference(source_path, another_target, 'cites')
    index = await kb_manager.read_index(source_path)
    assert len(index.references) == 2
    
    # Remove specific reference
    result = await kb_manager.remove_reference(source_path, target_path, 'references')
    assert result['status'] == 'updated'
    assert result['reference_count'] == 1
    
    # Verify reference was removed
    index = await kb_manager.read_index(source_path)
    assert len(index.references) == 1
    assert ImplicitRDFTriple(predicate='references', object=target_path.uri) not in index.references
    assert ImplicitRDFTriple(predicate='cites', object=another_target.uri) in index.references


@pytest.mark.asyncio
async def test_document_listing(kb_manager):
    """Test listing documents with various filters."""
    # Create documents in different namespaces and collections
    paths = [
        PathComponents.parse_path('docs/tech/python-guide'),
        PathComponents.parse_path('docs/tech/rust-guide'),
        PathComponents.parse_path('docs/personal/diary'),
        PathComponents.parse_path('notes/tech/snippets'),
        PathComponents.parse_path('notes/personal/ideas')
    ]
    
    for path in paths:
        await kb_manager.create_document(path, {'title': f'Document {path.name}'})
    
    # Test listing all documents
    all_docs = await kb_manager.list_documents()
    assert len(all_docs) == 5
    assert all(path.path in all_docs for path in paths)
    
    # Test listing with namespace filter
    docs_namespace = await kb_manager.list_documents(
        PartialPathComponents(namespace='docs')
    )
    assert len(docs_namespace) == 3
    assert 'docs/tech/python-guide' in docs_namespace
    assert 'docs/tech/rust-guide' in docs_namespace
    assert 'docs/personal/diary' in docs_namespace
    
    # Test listing with namespace and collection filter
    tech_docs = await kb_manager.list_documents(
        PartialPathComponents(namespace='docs', collection='tech')
    )
    assert len(tech_docs) == 2
    assert 'docs/tech/python-guide' in tech_docs
    assert 'docs/tech/rust-guide' in tech_docs
    
    # Test listing with non-recursive mode
    shallow_docs = await kb_manager.list_documents(
        PartialPathComponents(namespace='docs'),
        recursive=False
    )
    # In shallow mode, this should return collections within docs namespace
    assert 'docs/tech' in shallow_docs
    assert 'docs/personal' in shallow_docs


@pytest.mark.asyncio
async def test_document_moving(kb_manager):
    """Test moving documents to new locations."""
    # Create a document
    original_path = PathComponents.parse_path('temp/drafts/document')
    new_path = PathComponents.parse_path('published/articles/document')
    
    await kb_manager.create_document(original_path, {'title': 'Test Document'})
    await kb_manager.write_content(original_path, 'Document content')
    
    # Move the document
    moved_index = await kb_manager.move_document(original_path, new_path)
    
    # Verify document exists at new location
    new_index = await kb_manager.read_index(new_path)
    assert new_index.namespace == 'published'
    assert new_index.collection == 'articles'
    assert new_index.name == 'document'
    assert new_index.metadata['title'] == 'Test Document'
    
    # Verify content is still accessible
    content = await kb_manager.read_content(new_path)
    assert content == 'Document content'
    
    # Verify original location no longer exists
    with pytest.raises(FileNotFoundError):
        await kb_manager.read_index(original_path)


@pytest.mark.asyncio
async def test_datetime_consistency(kb_manager):
    """Test that datetime objects are properly timezone-aware throughout the system."""
    path = PathComponents.parse_path('test/datetime/document')
    
    # Create document
    before_create = datetime.now(timezone.utc)
    index = await kb_manager.create_document(path, {'title': 'DateTime Test'})
    after_create = datetime.now(timezone.utc)
    
    # Verify creation time is timezone-aware and within expected range
    assert index.created_at.tzinfo is not None
    assert index.updated_at.tzinfo is not None
    assert before_create <= index.created_at <= after_create
    assert before_create <= index.updated_at <= after_create
    
    # Update content and verify updated_at changes
    original_updated = index.updated_at
    await asyncio.sleep(0.01)  # Small delay to ensure time difference
    
    before_update = datetime.now(timezone.utc)
    await kb_manager.write_content(path, 'Updated content')
    after_update = datetime.now(timezone.utc)
    
    updated_index = await kb_manager.read_index(path)
    assert updated_index.updated_at > original_updated
    assert before_update <= updated_index.updated_at <= after_update
    assert updated_index.updated_at.tzinfo is not None


@pytest.mark.asyncio
async def test_error_handling(kb_manager):
    """Test proper error handling for various scenarios."""
    # Test reading non-existent document
    non_existent = PathComponents.parse_path('does/not/exist')
    with pytest.raises(FileNotFoundError):
        await kb_manager.read_index(non_existent)
    
    with pytest.raises(FileNotFoundError):
        await kb_manager.read_content(non_existent)
    
    # Test creating document with invalid path
    with pytest.raises(ValueError):
        PathComponents.parse_path('invalid path with spaces')
    
    # Test adding reference to non-existent document
    source_path = PathComponents.parse_path('test/error/source')
    await kb_manager.create_document(source_path, {'title': 'Source'})
    
    non_existent_target = PathComponents.parse_path('test/error/missing')
    with pytest.raises(FileNotFoundError):
        await kb_manager.add_reference(source_path, non_existent_target, 'references')
    
    # Test creating document where content already exists
    path = PathComponents.parse_path('test/error/duplicate')
    await kb_manager.create_document(path, {'title': 'Original'})
    
    with pytest.raises(ValueError):
        await kb_manager.create_document(path, {'title': 'Duplicate'})


@pytest.mark.asyncio 
async def test_content_check_operations(kb_manager):
    """Test content and index checking operations."""
    path = PathComponents.parse_path('test/check/document')
    
    # Initially, nothing should exist
    assert not await kb_manager.check_index(path)
    assert not await kb_manager.check_content(path)
    
    # After creating document, index should exist but not content
    await kb_manager.create_document(path, {'title': 'Check Test'})
    assert await kb_manager.check_index(path)
    assert not await kb_manager.check_content(path)
    
    # After writing content, both should exist
    await kb_manager.write_content(path, 'Test content')
    assert await kb_manager.check_index(path)
    assert await kb_manager.check_content(path)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get('RUN_SEARCH_TESTS', '').lower() in ('1', 'true', 'yes'),
    reason="Search tests require tantivy and sentence-transformers dependencies"
)
async def test_search_integration(kb_manager_with_search):
    """Test search functionality integration (requires search dependencies)."""
    # Create test documents
    docs = [
        ('tech/guides/python', 'Python programming guide with examples'),
        ('tech/guides/rust', 'Rust systems programming language tutorial'),
        ('tech/notes/async', 'Asynchronous programming patterns in Python'),
    ]
    
    for path_str, content in docs:
        path = PathComponents.parse_path(path_str)
        await kb_manager_with_search.create_document(path, {'title': path.name})
        await kb_manager_with_search.write_content(path, content)
    
    # Test search functionality
    results = await kb_manager_with_search.search(
        query="python programming",
        top_k_sparse=10,
        top_k_rerank=5,
        use_reranker=False  # Skip reranking to avoid model downloads in tests
    )
    
    # Should find documents related to Python
    assert len(results) > 0
    result_urns = [r['urn'] for r in results]
    assert any('python' in urn.lower() for urn in result_urns) 