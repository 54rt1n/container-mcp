"""Knowledge base tools for Container-MCP.

This module provides tools for interacting with the knowledge base, including
document operations like writing, reading, adding preferences and references.
"""

from typing import Dict, Any, Optional, List, Tuple
import time

from mcp.server.fastmcp import FastMCP
from cmcp.managers.knowledge_base_manager import KnowledgeBaseManager
from cmcp.kb.path import PathComponents, PartialPathComponents
from cmcp.kb.models import DocumentIndex, ImplicitRDFTriple

import logging

logger = logging.getLogger(__name__)

def create_kb_tools(mcp: FastMCP, kb_manager: KnowledgeBaseManager) -> None:
    """Create and register knowledge base tools.
    
    Args:
        mcp: The MCP instance
        kb_manager: The knowledge base manager instance
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
            Dictionary with document index
        """
        try:
            # Parse the path to get components
            components = PathComponents.parse_path(path)
            
            # Use default empty metadata if not provided
            if metadata is None:
                metadata = {}
            
            # Create document with metadata only
            index = await kb_manager.create_document(
                components=components,
                metadata=metadata
            )
            
            return index.model_dump()
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error creating document at {path}: {e}", exc_info=True, stack_info=True)
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
        try:
            # Parse the path to get components
            components = PathComponents.parse_path(path)
            
            # Check if document exists (index must exist)
            if not await kb_manager.check_index(components):
                return {
                    "status": "error",
                    "error": f"Document not found: {path}. Create it first using kb_create_document."
                }
            
            # Check if content already exists using the check_content method
            if await kb_manager.check_content(components) and not force:
                return {
                    "status": "error",
                    "error": f"Content already exists at path: {components.urn}. Use force=True to overwrite existing content."
                }
            
            # Write content with the components
            index = await kb_manager.write_content(
                components=components,
                content=content
            )

            return index.model_dump()
            
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
        except Exception as e:
            logger.error(f"Error writing content to {path}: {e}", exc_info=True, stack_info=True)
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
        try:
            # Parse the path to get components
            components = PathComponents.parse_path(path)
            
            # Update metadata with the components
            index = await kb_manager.update_metadata(
                components=components,
                metadata=metadata
            )
            
            return index.model_dump()
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
        except Exception as e:
            logger.error(f"Error updating metadata for {path}: {e}", exc_info=True, stack_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    @mcp.tool()
    async def kb_read_index(path: str) -> Dict[str, Any]:
        """Read a document index from the knowledge base.
        
        Args:
            path: Document path in format "namespace/collection[/subcollection]*/name"
            
        Returns:
            Dictionary with document content, metadata, and optional nextChunkNum
        """
        try:
            # Parse the path
            components = PathComponents.parse_path(path)
            
            # Read the document using components
            index = await kb_manager.read_index(components)
            
            return index.model_dump()
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error reading document at {path}: {e}", exc_info=True, stack_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    @mcp.tool()
    async def kb_read_content(path: str) -> Dict[str, Any]:
        """Read content from a document in the knowledge base.
        
        Args:
            path: Document path in format "namespace/collection[/subcollection]*/name"
            
        Returns:
            Document content as string
        """
        try:
            # Parse the path
            components = PathComponents.parse_path(path)
            
            # Read the document using components
            content = await kb_manager.read_content(components)
            
            return content
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error reading content from {path}: {e}", exc_info=True, stack_info=True)
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
        try:
            # Parse the path
            components = PathComponents.parse_path(path)
            
            # Create triple with the document URN as subject
            preferences = [ImplicitRDFTriple(predicate=predicate, object=object)]
            
            # Add preference using components
            result = await kb_manager.add_preference(
                components=components,
                preferences=preferences
            )
            
            return result
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error adding preference: {e}", exc_info=True, stack_info=True)
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
        try:
            # Parse the path
            components = PathComponents.parse_path(path)
            
            # Create triple with the document URN as subject
            preferences = [ImplicitRDFTriple(predicate=predicate, object=object)]
            
            # Remove preference using components
            result = await kb_manager.remove_preference(
                components=components,
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
        try:
            # Parse both paths
            components = PathComponents.parse_path(path)
            ref_components = PathComponents.parse_path(ref_path)
            
            # Add reference using components
            result = await kb_manager.add_reference(
                components=components,
                ref_components=ref_components,
                relation=relation
            )
            
            return result
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error adding reference: {e}", exc_info=True, stack_info=True)
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
        try:
            # Parse both paths
            components = PathComponents.parse_path(path)
            ref_components = PathComponents.parse_path(ref_path)
            
            # Remove reference using components
            result = await kb_manager.remove_reference(
                components=components,
                ref_components=ref_components,
                relation=relation
            )
            
            return result
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error removing reference: {e}", exc_info=True, stack_info=True)
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
        try:
            components = None
            
            if path:
                # Parse the path to get namespace/collection
                components = PartialPathComponents.parse_path(path)
            
            # List documents using components
            documents = await kb_manager.list_documents(
                components=components,
                recursive=recursive
            )
            
            return {"documents": documents, "count": len(documents)}
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error listing documents: {e}", exc_info=True, stack_info=True)
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
        try:
            # Parse both paths
            old_components = PathComponents.parse_path(path)
            new_components = PathComponents.parse_path(new_path)
            
            # Move document using components
            index = await kb_manager.move_document(
                components=old_components,
                new_components=new_components
            )
            
            return index.model_dump()
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error moving document: {e}", exc_info=True, stack_info=True)
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
        try:
            # Parse the path
            components = PathComponents.parse_path(path)
            
            # Delete the document using components
            result = await kb_manager.delete_document(components)
            
            return result
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
        except Exception as e:
            logger.error(f"Error deleting document: {e}", exc_info=True, stack_info=True)
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
            # Parse the path
            components = PathComponents.parse_path(f"kb://{path}")
            
            # Read the document using components
            document = await kb_manager.read_content(components)
            
            return document
        except Exception as e:
            logger.error(f"Error getting document content: {e}", exc_info=True, stack_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    # Add the kb_search tool at the end of the function
    @mcp.tool()
    async def kb_search(query: Optional[str] = None,
                      graph_filter_urns: Optional[List[str]] = None,
                      graph_expand_hops: int = 0,
                      relation_predicates: Optional[List[str]] = None,
                      top_k: int = 10,
                      use_reranker: bool = True) -> Dict[str, Any]:
        """Search the knowledge base using text query and/or graph expansion.

        Args:
            query: Text query for sparse search and reranking.
            graph_filter_urns: List of starting URNs for graph expansion/filtering.
            graph_expand_hops: Number of hops to expand graph relationships (default 0).
            relation_predicates: List of predicates to follow during graph traversal (default is "references").
            top_k: Number of results to return (after reranking if enabled).
            use_reranker: Whether to use semantic reranking (default True).

        Returns:
            Dictionary containing ranked list of document results.
        """
        try:
            # Decide sparse k based on reranking needs - fetch more initially
            top_k_sparse = max(50, top_k * 2) if use_reranker and query else top_k

            results = await kb_manager.search(
                query=query,
                graph_filter_urns=graph_filter_urns,
                graph_expand_hops=graph_expand_hops,
                relation_predicates=relation_predicates,
                top_k_sparse=top_k_sparse,
                top_k_rerank=top_k,  # Final desired K
                use_reranker=use_reranker
            )
            return {"results": results, "count": len(results)}
        except ValueError as e:
            return {"status": "error", "error": str(e)}
        except RuntimeError as e:
            return {"status": "error", "error": str(e)}
        except Exception as e:
            logger.error(f"Error during kb_search: {e}", exc_info=True)
            return {"status": "error", "error": f"An unexpected error occurred: {str(e)}"}