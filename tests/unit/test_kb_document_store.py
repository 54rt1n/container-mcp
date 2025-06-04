# tests/unit/test_kb_document_store.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Unit tests for KB DocumentStore."""

import pytest
import json
from datetime import datetime
from cmcp.kb.document_store import DocumentStore
from cmcp.kb.path import PathComponents, PartialPathComponents
from cmcp.kb.models import DocumentIndex, DocumentFragment

@pytest.fixture
def doc_store(tmp_path):
    """Fixture for DocumentStore using pytest's tmp_path."""
    store_path = tmp_path / "kb_store"
    store_path.mkdir()
    return DocumentStore(str(store_path))

@pytest.fixture
def sample_components():
    """Sample PathComponents."""
    return PathComponents.parse_path("ns1/col1/doc1")

@pytest.fixture
def sample_index(sample_components):
    """Sample DocumentIndex."""
    return DocumentIndex(
        namespace=sample_components.namespace,
        collection=sample_components.collection,
        name=sample_components.name,
        metadata={"key": "value"}
    )

def test_ensure_directory(doc_store, sample_components):
    """Test directory creation."""
    doc_path = doc_store.ensure_directory(sample_components)
    assert doc_path.exists()
    assert doc_path.is_dir()
    assert doc_path == doc_store.base_path / sample_components.path

def test_write_read_content(doc_store, sample_components):
    """Test writing and reading content."""
    content = "This is the document content."
    filename = doc_store.write_content(sample_components, content)
    assert filename == "content.0000.txt" # Default name

    read_content = doc_store.read_content(sample_components)
    assert read_content == content

    # Test with fragment
    frag_comp = PathComponents.parse_path("ns1/col1/doc1#frag1")
    frag_content = "Fragment content"
    frag_filename = doc_store.write_content(frag_comp, frag_content)
    assert frag_filename == "content.frag1.txt"

    read_frag_content = doc_store.read_content(frag_comp)
    assert read_frag_content == frag_content

    # Reading base path without fragment should maybe read first chunk? (Current impl does)
    read_base_again = doc_store.read_content(sample_components)
    assert read_base_again == content # Reads content.0000.txt first if no specific frag

    # Test reading non-existent content
    comp_no_content = PathComponents.parse_path("ns1/col1/doc_no_content")
    doc_store.ensure_directory(comp_no_content) # Ensure dir exists but no content
    with pytest.raises(FileNotFoundError):
        doc_store.read_content(comp_no_content)

def test_check_content(doc_store, sample_components):
    """Test checking content existence."""
    assert not doc_store.check_content(sample_components)
    doc_store.write_content(sample_components, "content")
    assert doc_store.check_content(sample_components)

def test_chunk_content(doc_store):
    """Test content chunking."""
    content = "a" * 5000
    chunks = doc_store.chunk_content(content, max_fragment_size=1000)
    assert len(chunks) == 5
    assert all(len(chunk) == 1000 for chunk in chunks)

    content = "a" * 1500
    chunks = doc_store.chunk_content(content, max_fragment_size=1000)
    assert len(chunks) == 2
    assert len(chunks[0]) == 1000
    assert len(chunks[1]) == 500

def test_write_read_index(doc_store, sample_components, sample_index):
    """Test writing and reading the index file."""
    index_path = doc_store.write_index(sample_components, sample_index)
    assert index_path.exists()
    assert index_path.name == "index.json"

    read_index_data = doc_store.read_index(sample_components)
    assert read_index_data.namespace == sample_index.namespace
    assert read_index_data.collection == sample_index.collection
    assert read_index_data.name == sample_index.name
    assert read_index_data.metadata == {"key": "value"}

    # Test reading non-existent index
    comp_no_index = PathComponents.parse_path("ns1/col1/doc_no_index")
    doc_store.ensure_directory(comp_no_index)
    with pytest.raises(FileNotFoundError):
        doc_store.read_index(comp_no_index)

def test_check_index(doc_store, sample_components, sample_index):
    """Test checking index existence."""
    assert not doc_store.check_index(sample_components)
    doc_store.write_index(sample_components, sample_index)
    assert doc_store.check_index(sample_components)

def test_update_index(doc_store, sample_components, sample_index):
    """Test updating the index file."""
    doc_store.write_index(sample_components, sample_index)
    original_updated_at = sample_index.updated_at

    update_data = {
        "metadata": {"key": "new_value", "added": True},
        "chunked": True
    }
    updated_index = doc_store.update_index(sample_components, update_data)

    assert updated_index.metadata == {"key": "new_value", "added": True}
    assert updated_index.chunked is True
    assert updated_index.updated_at > original_updated_at
    # Ensure path components weren't changed
    assert updated_index.namespace == sample_components.namespace
    assert updated_index.collection == sample_components.collection
    assert updated_index.name == sample_components.name

    # Read back to confirm persistence
    read_index = doc_store.read_index(sample_components)
    assert read_index.metadata == {"key": "new_value", "added": True}
    assert read_index.chunked is True

def test_find_documents_recursive(doc_store, sample_index):
    """Test recursive document finding."""
    comp1 = PathComponents.parse_path("ns1/col1/doc1")
    comp2 = PathComponents.parse_path("ns1/col1/doc2")
    comp3 = PathComponents.parse_path("ns1/col2/doc3")
    comp4 = PathComponents.parse_path("ns2/col1/doc4")
    doc_store.write_index(comp1, sample_index)
    doc_store.write_index(comp2, sample_index)
    doc_store.write_index(comp3, sample_index)
    doc_store.write_index(comp4, sample_index)

    # Find all
    all_docs = doc_store.find_documents_recursive(PartialPathComponents())
    assert set(all_docs) == {"ns1/col1/doc1", "ns1/col1/doc2", "ns1/col2/doc3", "ns2/col1/doc4"}

    # Filter by namespace - use explicit constructor
    ns1_docs = doc_store.find_documents_recursive(PartialPathComponents(namespace="ns1"))
    assert set(ns1_docs) == {"ns1/col1/doc1", "ns1/col1/doc2", "ns1/col2/doc3"}

    # Filter by namespace/collection - use explicit constructor  
    ns1_col1_docs = doc_store.find_documents_recursive(PartialPathComponents(namespace="ns1", collection="col1"))
    assert set(ns1_col1_docs) == {"ns1/col1/doc1", "ns1/col1/doc2"}

    # Filter by full path
    doc1_docs = doc_store.find_documents_recursive(PartialPathComponents.parse_path("ns1/col1/doc1"))
    assert set(doc1_docs) == {"ns1/col1/doc1"}

def test_find_documents_shallow(doc_store, sample_index):
    """Test shallow document finding."""
    comp1 = PathComponents.parse_path("ns1/col1/doc1")
    comp3 = PathComponents.parse_path("ns1/col2/doc3")
    comp4 = PathComponents.parse_path("ns2/col1/doc4")
    doc_store.write_index(comp1, sample_index)
    doc_store.write_index(comp3, sample_index)
    doc_store.write_index(comp4, sample_index)

    # List namespaces
    namespaces = doc_store.find_documents_shallow(PartialPathComponents())
    assert set(namespaces) == {"ns1", "ns2"}

    # List collections in ns1 - use explicit constructor
    ns1_collections = doc_store.find_documents_shallow(PartialPathComponents(namespace="ns1"))
    assert set(ns1_collections) == {"ns1/col1", "ns1/col2"}

    # List documents in ns1/col1 - use explicit constructor
    ns1_col1_docs = doc_store.find_documents_shallow(PartialPathComponents(namespace="ns1", collection="col1"))
    assert set(ns1_col1_docs) == {"ns1/col1/doc1"}

    # Find specific doc
    doc4 = doc_store.find_documents_shallow(PartialPathComponents.parse_path("ns2/col1/doc4"))
    assert set(doc4) == {"ns2/col1/doc4"}

    # Non-existent paths
    assert doc_store.find_documents_shallow(PartialPathComponents(namespace="ns3")) == []
    assert doc_store.find_documents_shallow(PartialPathComponents(namespace="ns1", collection="col3")) == []
    assert doc_store.find_documents_shallow(PartialPathComponents.parse_path("ns1/col1/docX")) == []

def test_delete_document(doc_store, sample_components, sample_index):
    """Test deleting a document."""
    doc_store.write_index(sample_components, sample_index)
    doc_store.write_content(sample_components, "content")
    doc_path = doc_store.base_path / sample_components.path
    assert doc_path.exists()

    doc_store.delete_document(sample_components)
    assert not doc_path.exists()

    # Verify parent directories are cleaned up if empty
    col_path = doc_path.parent
    ns_path = col_path.parent
    assert not col_path.exists()
    assert not ns_path.exists()

    # Test deleting non-existent document
    with pytest.raises(FileNotFoundError):
        doc_store.delete_document(PathComponents.parse_path("nsX/colX/docX"))

def test_delete_document_keeps_non_empty_parents(doc_store, sample_index):
    """Test deleting a document keeps non-empty parent directories."""
    comp1 = PathComponents.parse_path("ns1/col1/doc1")
    comp2 = PathComponents.parse_path("ns1/col1/doc2") # Sibling
    doc_store.write_index(comp1, sample_index)
    doc_store.write_index(comp2, sample_index)

    doc1_path = doc_store.base_path / comp1.path
    col1_path = doc1_path.parent
    ns1_path = col1_path.parent

    doc_store.delete_document(comp1)
    assert not doc1_path.exists()
    # Parents should still exist because doc2 is there
    assert col1_path.exists()
    assert ns1_path.exists()

def test_move_document(doc_store, sample_components, sample_index):
    """Test moving a document."""
    doc_store.write_index(sample_components, sample_index)
    doc_store.write_content(sample_components, "content")
    old_path = doc_store.base_path / sample_components.path

    new_components = PathComponents.parse_path("new_ns/new_col/new_name")
    new_path = doc_store.base_path / new_components.path

    assert old_path.exists()
    assert not new_path.exists()

    doc_store.move_document(sample_components, new_components)

    assert not old_path.exists()
    assert new_path.exists()
    assert (new_path / "index.json").exists()
    assert (new_path / "content.0000.txt").exists()

    # Verify index content was updated
    moved_index = doc_store.read_index(new_components)
    assert moved_index.namespace == new_components.namespace
    assert moved_index.collection == new_components.collection
    assert moved_index.name == new_components.name

    # Test moving non-existent
    with pytest.raises(FileNotFoundError):
        doc_store.move_document(PathComponents.parse_path("no/such/doc"), new_components)

    # Test moving to existing location
    doc_store.ensure_directory(sample_components) # Recreate dummy dir
    with pytest.raises(FileNotFoundError): # Should be FileExistsError, but depends on shutil.move / isdir check
        doc_store.move_document(new_components, sample_components) 