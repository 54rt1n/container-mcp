"""Knowledge base tools for Container-MCP.

This module provides tools for interacting with the knowledge base, including
document operations like writing, reading, adding preferences and references.
"""

from typing import Dict, Any, Optional, List, Tuple

from mcp.server.fastmcp import FastMCP
from cmcp.managers.knowledge_base_manager import KnowledgeBaseManager
from cmcp.kb.models import DocumentMetadata


def create_kb_tools(mcp: FastMCP) -> None:
    """Create and register knowledge base tools.
    
    Args:
        mcp: The MCP instance
    """
    @mcp.tool()
    async def kb_write_document(content: str, 
                              namespace: Optional[str] = None, 
                              collection: Optional[str] = None, 
                              name: Optional[str] = None, 
                              metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Write a document to the knowledge base.
        
        Args:
            content: Document content
            namespace: Document namespace (default: "documents")
            collection: Document collection (default: "general")
            name: Document name (if None, one will be generated)
            metadata: Optional document metadata
            
        Returns:
            Dictionary with document location and status
            
        Raises:
            ValueError: If any provided parameter is an empty string
        """
        # For write, we allow None values as they'll be auto-generated with defaults
        # But we don't allow empty strings
        for param_name, param_value in [
            ("namespace", namespace),
            ("collection", collection),
            ("name", name)
        ]:
            if param_value == "":
                return {
                    "status": "error",
                    "error": f"Parameter '{param_name}' cannot be an empty string"
                }
        
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        document_path = await kb_manager.write_document(
            content, 
            namespace=namespace, 
            collection=collection, 
            name=name, 
            metadata=metadata
        )
        
        # Parse the path to get individual components
        parts = document_path.split('/')
        if len(parts) >= 3:
            result_namespace = parts[0]
            result_collection = parts[1]
            result_name = parts[2]
        else:
            result_namespace = "documents"
            result_collection = "general"
            result_name = document_path
            
        return {
            "namespace": result_namespace,
            "collection": result_collection,
            "name": result_name,
            "status": "stored"
        }
    
    @mcp.tool()
    async def kb_read_document(namespace: str, 
                             collection: str, 
                             name: str, 
                             chunk_num: Optional[int] = None) -> Dict[str, Any]:
        """Read a document from the knowledge base.
        
        Args:
            namespace: Document namespace
            collection: Document collection
            name: Document name
            chunk_num: Optional chunk number to read
            
        Returns:
            Dictionary with document content, metadata, and optional nextChunkNum
            
        Raises:
            ValueError: If namespace, collection, or name is an empty string
        """
        # Validate inputs - no empty strings allowed
        for param_name, param_value in [
            ("namespace", namespace),
            ("collection", collection),
            ("name", name)
        ]:
            if param_value == "":
                return {
                    "status": "error",
                    "error": f"Parameter '{param_name}' cannot be an empty string"
                }
        
        try:
            kb_manager = KnowledgeBaseManager.from_env()
            await kb_manager.initialize()
            document_path = f"{namespace}/{collection}/{name}"
            document = await kb_manager.read_document(document_path, chunk_num)
            return document
        except Exception as e:
            return {
                "error": "The document was invalid. Please repair the document metadata.",
                "detail": str(e)
            }
    
    @mcp.tool()
    async def kb_add_preference(namespace: str, 
                              collection: str, 
                              name: str, 
                              subject: str, 
                              predicate: str, 
                              object: str) -> Dict[str, Any]:
        """Add a preference triple to a document.
        
        Args:
            namespace: Document namespace
            collection: Document collection
            name: Document name
            subject: Subject of the preference triple
            predicate: Predicate of the preference triple
            object: Object of the preference triple
            
        Returns:
            Dictionary with status and updated preference count
            
        Raises:
            ValueError: If any parameter is an empty string
        """
        # Validate inputs - no empty strings allowed
        for param_name, param_value in [
            ("namespace", namespace),
            ("collection", collection),
            ("name", name),
            ("subject", subject),
            ("predicate", predicate),
            ("object", object)
        ]:
            if param_value == "":
                return {
                    "status": "error",
                    "error": f"Parameter '{param_name}' cannot be an empty string"
                }
        
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        document_path = f"{namespace}/{collection}/{name}"
        # Create a list containing a single triple
        triple = [(subject, predicate, object)]
        result = await kb_manager.add_preference(document_path, triple)
        return result
    
    @mcp.tool()
    async def kb_remove_preference(namespace: str, 
                                 collection: str, 
                                 name: str, 
                                 subject: str, 
                                 predicate: str, 
                                 object: str) -> Dict[str, Any]:
        """Remove references from a document matching the specified attributes.
        
        Args:
            namespace: Document namespace
            collection: Document collection
            name: Document name
            subject: Subject of the preference triple to remove
            predicate: Predicate of the preference triple to remove
            object: Object of the preference triple to remove
            
        Returns:
            Dictionary with status and remaining preference count
            
        Raises:
            ValueError: If any parameter is an empty string
        """
        # Validate inputs - no empty strings allowed
        for param_name, param_value in [
            ("namespace", namespace),
            ("collection", collection),
            ("name", name),
            ("subject", subject),
            ("predicate", predicate),
            ("object", object)
        ]:
            if param_value == "":
                return {
                    "status": "error",
                    "error": f"Parameter '{param_name}' cannot be an empty string"
                }
        
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        document_path = f"{namespace}/{collection}/{name}"
        # Create a list containing a single triple
        triple = [(subject, predicate, object)]
        result = await kb_manager.remove_preference(document_path, triple)
        return result
    
    @mcp.tool()
    async def kb_remove_all_preferences(namespace: str, 
                                      collection: str, 
                                      name: str) -> Dict[str, Any]:
        """Remove all preference triples from a document.
        
        Args:
            namespace: Document namespace
            collection: Document collection
            name: Document name
            
        Returns:
            Dictionary with status and remaining preference count
            
        Raises:
            ValueError: If any parameter is an empty string
        """
        # Validate inputs - no empty strings allowed
        for param_name, param_value in [
            ("namespace", namespace),
            ("collection", collection),
            ("name", name)
        ]:
            if param_value == "":
                return {
                    "status": "error",
                    "error": f"Parameter '{param_name}' cannot be an empty string"
                }
        
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        document_path = f"{namespace}/{collection}/{name}"
        
        # Remove all preferences
        result = await kb_manager.remove_preference(document_path, None)
        return result
    
    @mcp.tool()
    async def kb_add_reference(namespace: str, 
                             collection: str, 
                             name: str, 
                             ref_namespace: str, 
                             ref_collection: str, 
                             ref_name: str, 
                             relation: str) -> Dict[str, Any]:
        """Add a reference to another document.
        
        Args:
            namespace: Source document namespace
            collection: Source document collection
            name: Source document name
            ref_namespace: Referenced document namespace
            ref_collection: Referenced document collection
            ref_name: Referenced document name
            relation: Relation predicate connecting the documents
            
        Returns:
            Dictionary with status and updated reference count
            
        Raises:
            ValueError: If any parameter is an empty string
        """
        # Validate inputs - no empty strings allowed
        for param_name, param_value in [
            ("namespace", namespace),
            ("collection", collection),
            ("name", name),
            ("ref_namespace", ref_namespace),
            ("ref_collection", ref_collection),
            ("ref_name", ref_name),
            ("relation", relation)
        ]:
            if param_value == "":
                return {
                    "status": "error",
                    "error": f"Parameter '{param_name}' cannot be an empty string"
                }
        
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        document_path = f"{namespace}/{collection}/{name}"
        ref_path = f"{ref_namespace}/{ref_collection}/{ref_name}"
        
        try:
            result = await kb_manager.add_reference(
                path=document_path, 
                ref_path=ref_path,
                relation=relation
            )
            return result
        except (FileNotFoundError, ValueError) as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    @mcp.tool()
    async def kb_remove_reference(namespace: str, 
                                collection: str, 
                                name: str, 
                                ref_namespace: str, 
                                ref_collection: str, 
                                ref_name: str, 
                                relation: str) -> Dict[str, Any]:
        """Remove references from a document matching the specified attributes.
        
        Args:
            namespace: Source document namespace
            collection: Source document collection
            name: Source document name
            ref_namespace: Referenced document namespace
            ref_collection: Referenced document collection
            ref_name: Referenced document name
            relation: Relation predicate
            
        Returns:
            Dictionary with status and remaining reference count
            
        Raises:
            ValueError: If any parameter is an empty string
        """
        # Validate inputs - no empty strings allowed
        for param_name, param_value in [
            ("namespace", namespace),
            ("collection", collection),
            ("name", name),
            ("ref_namespace", ref_namespace),
            ("ref_collection", ref_collection),
            ("ref_name", ref_name),
            ("relation", relation)
        ]:
            if param_value == "":
                return {
                    "status": "error",
                    "error": f"Parameter '{param_name}' cannot be an empty string"
                }
        
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        document_path = f"{namespace}/{collection}/{name}"
        ref_path = f"{ref_namespace}/{ref_collection}/{ref_name}"
        
        result = await kb_manager.remove_reference(
            path=document_path,
            ref_path=ref_path,
            ref_namespace=ref_namespace,
            ref_collection=ref_collection,
            ref_name=ref_name,
            relation=relation
        )
        
        return result
    
    @mcp.tool()
    async def kb_list_documents(namespace: Optional[str] = None, 
                              collection: Optional[str] = None, 
                              recursive: bool = True) -> Dict[str, Any]:
        """List documents in the knowledge base.
        
        Args:
            namespace: Optional namespace to filter by
            collection: Optional collection to filter by (requires namespace)
            recursive: Whether to list recursively
            
        Returns:
            Dictionary with list of document locations
            
        Raises:
            ValueError: If any provided parameter is an empty string
        """
        # Validate inputs if provided - no empty strings allowed
        if namespace == "":
            return {
                "status": "error",
                "error": "Parameter 'namespace' cannot be an empty string"
            }
        
        if collection == "":
            return {
                "status": "error",
                "error": "Parameter 'collection' cannot be an empty string"
            }
        
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        
        document_paths = await kb_manager.list_documents(
            namespace=namespace, 
            collection=collection, 
            recursive=recursive
        )
        
        # Parse paths into components
        documents = []
        for path in document_paths:
            parts = path.split('/')
            if len(parts) >= 3:
                documents.append({
                    "namespace": parts[0],
                    "collection": parts[1],
                    "name": parts[2]
                })
        
        return {"documents": documents, "count": len(documents)}
    
    @mcp.tool()
    async def kb_move_document(namespace: str, 
                             collection: str, 
                             name: str, 
                             new_namespace: Optional[str] = None, 
                             new_collection: Optional[str] = None, 
                             new_name: Optional[str] = None) -> Dict[str, Any]:
        """Move a document to a new location in the knowledge base.
        
        Args:
            namespace: Current document namespace
            collection: Current document collection
            name: Current document name
            new_namespace: New namespace (if None, keeps current)
            new_collection: New collection (if None, keeps current)
            new_name: New name (if None, keeps current)
            
        Returns:
            Dictionary with old and new document locations
            
        Raises:
            ValueError: If any required parameter is an empty string or if any optional parameter is an empty string
        """
        # Validate required inputs - no empty strings allowed
        for param_name, param_value in [
            ("namespace", namespace),
            ("collection", collection),
            ("name", name)
        ]:
            if param_value == "":
                return {
                    "status": "error",
                    "error": f"Parameter '{param_name}' cannot be an empty string"
                }
        
        # Validate optional inputs if provided
        for param_name, param_value in [
            ("new_namespace", new_namespace),
            ("new_collection", new_collection),
            ("new_name", new_name)
        ]:
            if param_value == "":
                return {
                    "status": "error",
                    "error": f"Parameter '{param_name}' cannot be an empty string"
                }
        
        kb_manager = KnowledgeBaseManager.from_env()
        await kb_manager.initialize()
        current_path = f"{namespace}/{collection}/{name}"
        
        new_path = await kb_manager.move_document(
            current_path=current_path,
            new_namespace=new_namespace,
            new_collection=new_collection,
            new_name=new_name
        )
        
        # Parse new path
        new_parts = new_path.split('/')
        if len(new_parts) >= 3:
            result_namespace = new_parts[0]
            result_collection = new_parts[1]
            result_name = new_parts[2]
        else:
            result_namespace = new_namespace or namespace
            result_collection = new_collection or collection
            result_name = new_name or name
        
        return {
            "old_namespace": namespace,
            "old_collection": collection,
            "old_name": name,
            "new_namespace": result_namespace,
            "new_collection": result_collection,
            "new_name": result_name,
            "status": "moved"
        }
    
    # Register knowledge base document resource handler
    @mcp.resource("kb://{namespace}/{collection}/{name}")
    async def get_kb_document(namespace: str, collection: str, name: str) -> str:
        """Get knowledge base document contents as a resource.
        
        Args:
            namespace: Document namespace
            collection: Document collection
            name: Document name
            
        Returns:
            Document content as string
        """
        try:
            kb_manager = KnowledgeBaseManager.from_env()
            await kb_manager.initialize()
            document_path = f"{namespace}/{collection}/{name}"
            document = await kb_manager.read_document(document_path)
            return document.get("content", f"Error: Could not retrieve content for {namespace}/{collection}/{name}")
        except Exception as e:
            return f"Error: {str(e)}" 