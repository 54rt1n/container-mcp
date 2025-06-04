# tests/unit/test_kb_models.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Unit tests for KB models."""

import pytest
from datetime import datetime, timezone
from cmcp.kb.models import (
    DocumentFragment,
    ImplicitRDFTriple,
    DocumentIndex
)

def test_document_fragment_instantiation():
    """Test creating a DocumentFragment."""
    frag = DocumentFragment(size=1024, sequence_num=0)
    assert frag.size == 1024
    assert frag.sequence_num == 0

def test_implicit_rdf_triple_instantiation():
    """Test creating an ImplicitRDFTriple."""
    triple = ImplicitRDFTriple(predicate="relatesTo", object="kb://ns/coll/doc2")
    assert triple.predicate == "relatesTo"
    assert triple.object == "kb://ns/coll/doc2"

def test_document_index_instantiation_defaults():
    """Test creating a DocumentIndex with minimal required fields and defaults."""
    now = datetime.now(timezone.utc)
    index = DocumentIndex(name="test-doc") # namespace and collection have defaults

    assert index.name == "test-doc"
    assert index.namespace == "documents" # Default
    assert index.collection == "general"   # Default
    assert index.type == "document"
    assert index.subtype == "text"
    assert (now - index.created_at).total_seconds() < 1
    assert (now - index.updated_at).total_seconds() < 1
    assert index.content_type == "text/plain"
    assert index.chunked is False
    assert index.fragments == {}
    assert index.preferences == []
    assert index.references == []
    assert index.indices == []
    assert index.metadata == {}

def test_document_index_instantiation_custom():
    """Test creating a DocumentIndex with custom values."""
    created = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    updated = datetime(2023, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
    frag = DocumentFragment(size=500, sequence_num=0)
    pref = ImplicitRDFTriple(predicate="p1", object="o1")
    ref = ImplicitRDFTriple(predicate="r1", object="kb://other/coll/doc")
    idx = ImplicitRDFTriple(predicate="i1", object="v1")
    meta = {"custom": "value", "num": 123}

    index = DocumentIndex(
        namespace="custom_ns",
        collection="custom_coll/sub",
        name="custom-doc",
        type="report",
        subtype="pdf",
        created_at=created,
        updated_at=updated,
        content_type="application/pdf",
        chunked=True,
        fragments={"frag0.pdf": frag},
        preferences=[pref],
        references=[ref],
        indices=[idx],
        metadata=meta
    )

    assert index.namespace == "custom_ns"
    assert index.collection == "custom_coll/sub"
    assert index.name == "custom-doc"
    assert index.type == "report"
    assert index.subtype == "pdf"
    assert index.created_at == created
    assert index.updated_at == updated
    assert index.content_type == "application/pdf"
    assert index.chunked is True
    assert index.fragments == {"frag0.pdf": frag}
    assert index.preferences == [pref]
    assert index.references == [ref]
    assert index.indices == [idx]
    assert index.metadata == meta 