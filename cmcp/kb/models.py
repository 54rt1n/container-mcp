# cmcp/kb/models.py
# container-mcp © 2025 by Martin Bukowski is licensed under Apache 2.0

"""Pydantic models for the knowledge base document store."""

from datetime import datetime, timezone
from typing import List, NamedTuple, Dict, Any
from pydantic import BaseModel, Field

class DocumentFragment(BaseModel):
    """Represents a fragment of a document content."""
    
    size: int = Field(..., description="Size of the fragment in bytes")
    sequence_num: int = Field(..., description="Sequence number of the fragment")

class RDFTriple(NamedTuple):
    """Represents a triple of an RDF graph."""
    
    subject: str
    predicate: str
    object: str

class ImplicitRDFTriple(NamedTuple):
    """Represents an implicit triple of an RDF graph, where the subject is the document."""
    
    predicate: str
    object: str

class DocumentIndex(BaseModel):
    """Represents metadata for a knowledge base document."""
    
    namespace: str = Field("documents", description="Top-level category for the document")
    collection: str = Field("general", description="Collection within the namespace")
    name: str = Field(..., description="Unique name for the document within its collection")
    type: str = Field("document", description="Type of the resource")
    subtype: str = Field("text", description="Subtype of the document")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp")
    content_type: str = Field("text/plain", description="MIME type of the content")
    chunked: bool = Field(False, description="Whether the document is split into fragments")
    fragments: Dict[str, DocumentFragment] = Field(default_factory=dict, description="A dictionary of filename -> fragment information")
    preferences: List[ImplicitRDFTriple] = Field(
        default_factory=list, 
        description="RDF triples associated with the document"
    )
    references: List[ImplicitRDFTriple] = Field(
        default_factory=list, 
        description="References to other documents"
    )
    referenced_by: List[ImplicitRDFTriple] = Field(
        default_factory=list, 
        description="Documents that reference this document (bidirectional references)"
    )
    indices: List[ImplicitRDFTriple] = Field(
        default_factory=list, 
        description="Indexing triples for the document"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Additional custom metadata for the document"
    )