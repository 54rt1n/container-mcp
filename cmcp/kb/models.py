"""Pydantic models for the knowledge base document store."""

from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """Represents a chunk of a document content."""
    
    path: str = Field(..., description="Path identifier for this chunk")
    size: int = Field(..., description="Size of the chunk in bytes")
    sequence_num: int = Field(..., description="Sequence number of the chunk")


class DocumentMetadata(BaseModel):
    """Represents metadata for a knowledge base document."""
    
    namespace: str = Field("documents", description="Top-level category for the document")
    collection: str = Field("general", description="Collection within the namespace")
    name: str = Field(..., description="Unique name for the document within its collection")
    type: str = Field("document", description="Type of the resource")
    subtype: str = Field("text", description="Subtype of the document")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    content_type: str = Field("text/plain", description="MIME type of the content")
    chunked: bool = Field(False, description="Whether the document is split into chunks")
    chunks: List[DocumentChunk] = Field(default_factory=list, description="List of chunks if document is chunked")
    preferences: List[Tuple[str, str, str]] = Field(
        default_factory=list, 
        description="RDF triples associated with the document"
    )
    references: List[Tuple[str, str, str]] = Field(
        default_factory=list, 
        description="References to other documents"
    )
    indices: List[Tuple[str, str, str]] = Field(
        default_factory=list, 
        description="Indexing triples for the document"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Additional custom metadata for the document"
    )
    
    @property
    def path(self) -> str:
        """Get the full path of the document."""
        return f"{self.namespace}/{self.collection}/{self.name}"