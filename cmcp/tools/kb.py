"""Knowledge base tools for Container-MCP.

This module provides tools for interacting with the knowledge base, including
document operations like writing, reading, adding preferences and references.
"""

from typing import Dict, Any, Optional, List, Tuple
import time

from mcp.server.fastmcp import FastMCP
from cmcp.managers.knowledge_base_manager import KnowledgeBaseManager
from cmcp.kb.path import PathComponents
from cmcp.kb.models import DocumentMetadata, ImplicitRDFTriple


def create_kb_tools(mcp: FastMCP) -> None:
    """Create and register knowledge base tools.
    
    Args:
        mcp: The MCP instance
    """
    
    @mcp.tool()
    async def kb_create_document(path: str,
                              metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new document in the knowledge base (metadata only, no content).
        
        Note: This is a two-step process. First create the document with metadata using this function,
        then add content using kb_write_content. This approach prevents wasting tokens if document
        creation fails (e.g., if the document already exists or the path is invalid).
        
        Args:
            path: Document path in format "namespace/collection[/subcollection]*/name"
            metadata: Optional document metadata (default: {})
            
        Returns:
            Dictionary with document location and status
        """
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        
        try:
            # Parse the path to get components
            components = await PathComponents.parse_path(path)
            
            # Use default empty metadata if not provided
            if metadata is None:
                metadata = {}
            
            # Create document with metadata only
            document_path = await kb_manager.create_document(
                components=components,
                metadata=metadata
            )
            
            # Parse the generated path to get the components
            result_components = await PathComponents.parse_path(document_path)
            
            return {
                "path": result_components.path,
                "urn": result_components.urn,
                "namespace": result_components.namespace,
                "collection": result_components.collection,
                "name": result_components.name,
                "status": "created",
                "message": "Document created successfully. Use kb_write_content to add content."
            }
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    @mcp.tool()
    async def kb_update_document(path: str,
                              content: Optional[str] = None,
                              metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Write a document to the knowledge base at a specific path.
        
        Args:
            path: Document path in format "namespace/collection[/subcollection]*/name"
            content: Optional document content
            metadata: Optional document metadata
            
        Returns:
            Dictionary with document location and status
        """
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        
        try:
            # Parse the path to get components
            components = await PathComponents.parse_path(path)
            
            # Write document with the components
            document_path = await kb_manager.write_document(
                content,
                namespace=components.namespace,
                collection=components.collection,
                name=components.name,
                metadata=metadata
            )
            
            # Get the final components
            result_components = await PathComponents.parse_path(document_path)
            
            return {
                "path": result_components.path,
                "urn": result_components.urn,
                "namespace": result_components.namespace,
                "collection": result_components.collection,
                "name": result_components.name,
                "status": "stored"
            }
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    @mcp.tool()
    async def kb_write_content(path: str,
                             content: str,
                             force: bool = False) -> Dict[str, Any]:
        """Write content to an existing document in the knowledge base.
        
        Note: This is part of a two-step process. First create the document with metadata using
        kb_create_document, then add content using this function. This approach prevents wasting 
        tokens if document creation fails.
        
        Args:
            path: Document path in format "namespace/collection[/subcollection]*/name"
            content: Document content
            force: Whether to overwrite existing content if it exists
            
        Returns:
            Dictionary with document location and status
        """
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        
        try:
            # Parse the path to get components
            components = await PathComponents.parse_path(path)
            
            # Check if document exists (metadata must exist)
            try:
                # Only check if metadata exists, not content
                kb_manager.document_store.read_metadata(components)
            except FileNotFoundError:
                return {
                    "status": "error",
                    "error": f"Document not found: {path}. Create it first using kb_create_document."
                }
            
            # Check if content already exists using the read_content method
            existing_content = await kb_manager.read_content(components)
            
            if existing_content is not None and not force:
                return {
                    "status": "error",
                    "error": f"Content already exists at path: {components.urn}. Use force=True to overwrite existing content."
                }
            
            # Write content with the components
            document_path = await kb_manager.write_content(
                content,
                namespace=components.namespace,
                collection=components.collection,
                name=components.name
            )
            
            # Get the final components
            result_components = await PathComponents.parse_path(document_path)
            
            return {
                "path": result_components.path,
                "urn": result_components.urn,
                "namespace": result_components.namespace,
                "collection": result_components.collection,
                "name": result_components.name,
                "status": "content_updated"
            }
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
        except FileNotFoundError as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    @mcp.tool()
    async def kb_update_metadata(path: str,
                               metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Update metadata for a document in the knowledge base.
        
        Args:
            path: Document path in format "namespace/collection[/subcollection]*/name"
            metadata: Document metadata
            
        Returns:
            Dictionary with document location and status
        """
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        
        try:
            # Parse the path to get components
            components = await PathComponents.parse_path(path)
            
            # Update metadata with the components
            document_path = await kb_manager.update_metadata(
                namespace=components.namespace,
                collection=components.collection,
                name=components.name,
                metadata=metadata
            )
            
            # Get the final components
            result_components = await PathComponents.parse_path(document_path)
            
            return {
                "path": result_components.path,
                "urn": result_components.urn,
                "namespace": result_components.namespace,
                "collection": result_components.collection,
                "name": result_components.name,
                "status": "metadata_updated"
            }
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
        except FileNotFoundError as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    @mcp.tool()
    async def kb_read_document(path: str,
                             chunk_num: Optional[int] = None) -> Dict[str, Any]:
        """Read a document from the knowledge base.
        
        Args:
            path: Document path in format "namespace/collection[/subcollection]*/name"
            chunk_num: Optional chunk number to read
            
        Returns:
            Dictionary with document content, metadata, and optional nextChunkNum
        """
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        
        try:
            # Parse the path
            components = await PathComponents.parse_path(path)
            
            # Read the document using components
            document = await kb_manager.read_document(
                namespace=components.namespace,
                collection=components.collection,
                name=components.name,
                chunk_num=chunk_num
            )
            
            # Add URN to the response
            if "metadata" in document:
                document["urn"] = components.urn
                document["path"] = components.path
            
            return document
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    @mcp.tool()
    async def kb_add_preference(path: str,
                              predicate: str,
                              object: str) -> Dict[str, Any]:
        """Add a preference triple to a document.
        
        Args:
            path: Document path (which becomes the subject of the triple)
            predicate: Predicate of the preference triple
            object: Object of the preference triple
            
        Returns:
            Dictionary with status and updated preference count
        """
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        
        try:
            # Parse the path
            components = await PathComponents.parse_path(path)
            
            # Create triple with the document URN as subject
            preferences = [ImplicitRDFTriple(predicate=predicate, object=object)]
            
            # Add preference using components
            result = await kb_manager.add_preference(
                namespace=components.namespace,
                collection=components.collection,
                name=components.name,
                preferences=preferences
            )
            
            return result
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    @mcp.tool()
    async def kb_remove_preference(path: str,
                                 predicate: str,
                                 object: str) -> Dict[str, Any]:
        """Remove a preference triple from a document.
        
        Args:
            path: Document path (which is the subject of the triple)
            predicate: Predicate of the preference triple to remove
            object: Object of the preference triple to remove
            
        Returns:
            Dictionary with status and remaining preference count
        """
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        
        try:
            # Parse the path
            components = await PathComponents.parse_path(path)
            
            # Create triple with the document URN as subject
            preferences = [ImplicitRDFTriple(predicate=predicate, object=object)]
            
            # Remove preference using components
            result = await kb_manager.remove_preference(
                namespace=components.namespace,
                collection=components.collection,
                name=components.name,
                preferences=preferences
            )
            
            return result
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    @mcp.tool()
    async def kb_add_reference(path: str,
                             ref_path: str,
                             relation: str) -> Dict[str, Any]:
        """Add a reference to another document.
        
        Args:
            path: Source document path
            ref_path: Referenced document path
            relation: Relation predicate connecting the documents
            
        Returns:
            Dictionary with status and updated reference count
        """
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        
        try:
            # Parse both paths
            components = await PathComponents.parse_path(path)
            ref_components = await PathComponents.parse_path(ref_path)
            
            # Add reference using components
            result = await kb_manager.add_reference(
                namespace=components.namespace,
                collection=components.collection,
                name=components.name,
                ref_namespace=ref_components.namespace,
                ref_collection=ref_components.collection,
                ref_name=ref_components.name,
                relation=relation
            )
            
            return result
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    @mcp.tool()
    async def kb_remove_reference(path: str,
                                ref_path: str,
                                relation: str) -> Dict[str, Any]:
        """Remove references from a document matching the specified attributes.
        
        Args:
            path: Source document path
            ref_path: Referenced document path
            relation: Relation predicate
            
        Returns:
            Dictionary with status and remaining reference count
        """
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        
        try:
            # Parse both paths
            components = await PathComponents.parse_path(path)
            ref_components = await PathComponents.parse_path(ref_path)
            
            # Remove reference using components
            result = await kb_manager.remove_reference(
                namespace=components.namespace,
                collection=components.collection,
                name=components.name,
                ref_namespace=ref_components.namespace,
                ref_collection=ref_components.collection,
                ref_name=ref_components.name,
                relation=relation
            )
            
            return result
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    @mcp.tool()
    async def kb_list_documents(path: Optional[str] = None,
                              recursive: bool = True) -> Dict[str, Any]:
        """List documents in the knowledge base.
        
        Args:
            path: Optional path prefix to filter by
            recursive: Whether to list recursively
            
        Returns:
            Dictionary with list of document locations
        """
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        
        try:
            namespace = None
            collection = None
            
            if path:
                # Parse the path to get namespace/collection
                components = await PathComponents.parse_path(path)
                namespace = components.namespace
                collection = components.collection
            
            # List documents using components
            document_paths = await kb_manager.list_documents(
                namespace=namespace,
                collection=collection,
                recursive=recursive
            )
            
            # Parse paths into components
            documents = []
            for doc_path in document_paths:
                doc_components = await PathComponents.parse_path(doc_path)
                documents.append({
                    "path": doc_components.path,
                    "urn": doc_components.urn,
                    "namespace": doc_components.namespace,
                    "collection": doc_components.collection,
                    "name": doc_components.name
                })
            
            return {"documents": documents, "count": len(documents)}
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    @mcp.tool()
    async def kb_move_document(path: str,
                             new_path: str) -> Dict[str, Any]:
        """Move a document to a new location in the knowledge base.
        
        Args:
            path: Current document path
            new_path: New document path
            
        Returns:
            Dictionary with old and new document locations
        """
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        
        try:
            # Parse both paths
            old_components = await PathComponents.parse_path(path)
            new_components = await PathComponents.parse_path(new_path)
            
            # Move document using components
            result_path = await kb_manager.move_document(
                namespace=old_components.namespace,
                collection=old_components.collection,
                name=old_components.name,
                new_namespace=new_components.namespace,
                new_collection=new_components.collection,
                new_name=new_components.name
            )
            
            # Parse result path
            result_components = await PathComponents.parse_path(result_path)
            
            return {
                "old_path": old_components.path,
                "old_urn": old_components.urn,
                "old_namespace": old_components.namespace,
                "old_collection": old_components.collection,
                "old_name": old_components.name,
                "new_path": result_components.path,
                "new_urn": result_components.urn,
                "new_namespace": result_components.namespace,
                "new_collection": result_components.collection,
                "new_name": result_components.name,
                "status": "moved"
            }
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    @mcp.tool()
    async def kb_delete_document(path: str) -> Dict[str, Any]:
        """Delete a document from the knowledge base.
        
        Args:
            path: Document path in format "namespace/collection[/subcollection]*/name"
            
        Returns:
            Dictionary with deleted document information and status
        """
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        
        try:
            # Parse the path
            components = await PathComponents.parse_path(path)
            
            # Delete the document using components
            result = await kb_manager.delete_document(
                namespace=components.namespace,
                collection=components.collection,
                name=components.name
            )
            
            return {
                "path": components.path,
                "urn": components.urn,
                "namespace": components.namespace,
                "collection": components.collection,
                "name": components.name,
                "status": "deleted"
            }
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
        except FileNotFoundError as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    # Register knowledge base document resource handler
    @mcp.resource("kb://{path}")
    async def get_kb_document(path: str) -> str:
        """Get knowledge base document contents as a resource.
        
        Args:
            path: Document path
            
        Returns:
            Document content as string
        """
        try:
            kb_manager = KnowledgeBaseManager.from_env()
            await kb_manager.initialize()
            
            # Parse the path
            components = await PathComponents.parse_path(path)
            
            # Read the document using components
            document = await kb_manager.read_document(
                namespace=components.namespace,
                collection=components.collection,
                name=components.name
            )
            
            return document.get("content", f"Error: Could not retrieve content for {components.urn}")
        except Exception as e:
            return f"Error: {str(e)}"