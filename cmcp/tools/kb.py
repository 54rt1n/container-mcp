"""Knowledge base tools for Container-MCP.

This module provides tools for interacting with the knowledge base, including
document operations like writing, reading, adding preferences and references.
"""

from typing import Dict, Any, Optional, List, Tuple
import time

from mcp.server.fastmcp import FastMCP
from cmcp.managers.knowledge_base_manager_v2 import KnowledgeBaseManagerV2 as KnowledgeBaseManager
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
    
    @mcp.tool()
    async def kb_search(query: Optional[str] = None,
                      graph_seed_urns: Optional[List[str]] = None,
                      graph_expand_hops: int = 0,
                      filter_urns: Optional[List[str]] = None,
                      relation_predicates: Optional[List[str]] = None,
                      top_k_sparse: int = 50,
                      top_k_rerank: int = 10,
                      include_content: bool = False,
                      include_index: bool = False,
                      use_reranker: bool = True) -> Dict[str, Any]:
        """Search the knowledge base using text query and/or graph expansion.

        Args:
            query: Text query for sparse search and reranking.
            graph_seed_urns: List of starting URNs for graph expansion/filtering.
            graph_expand_hops: Number of hops to expand graph relationships (default 0).
            filter_urns: List of URNs to exclude from search results.
            relation_predicates: List of predicates to follow during graph traversal (default is "references").
            top_k_sparse: The number of candidates to retrieve from the initial sparse search (default 50).
            top_k_rerank: The final number of results to return after reranking (default 10).
            include_content: Whether to include document content in results (default False).
            include_index: Whether to include document index/metadata in results (default False).
            use_reranker: Whether to use semantic reranking (default True).

        Returns:
            Dictionary containing ranked list of document results.
        """
        try:
            results = await kb_manager.search(
                query=query,
                graph_seed_urns=graph_seed_urns,
                graph_expand_hops=graph_expand_hops,
                filter_urns=filter_urns,
                relation_predicates=relation_predicates,
                top_k_sparse=top_k_sparse,
                top_k_rerank=top_k_rerank,
                include_content=include_content,
                include_index=include_index,
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

    @mcp.tool()
    async def kb_read(path: Optional[str] = None,
                     recursive: bool = True,
                     include_content: bool = False,
                     include_index: bool = False) -> Dict[str, Any]:
        """Read from the knowledge base - either list documents or read specific document data.
        
        This function intelligently handles both listing and reading based on the path:
        - If path is None, partial, or points to a namespace/collection: lists documents
        - If path points to a specific document: reads document content/metadata
        
        Args:
            path: Document/collection path. None lists all documents.
            recursive: Whether to list recursively (for listing mode)
            include_content: Whether to include document content (for reading mode)
            include_index: Whether to include document metadata (for reading mode)
            
        Returns:
            Dictionary with either document list or document data
        """
        async def _process_document_list(documents, include_content, include_index):
            """Helper to process a list of documents and optionally include their content/index."""
            if not include_content and not include_index:
                # Simple list mode
                return {"documents": documents, "count": len(documents), "mode": "list"}
            
            # Bulk read mode - fetch content/index for each document
            processed_docs = []
            for doc_path in documents:
                try:
                    components = PathComponents.parse_path(doc_path)
                    doc_data = {"path": doc_path}
                    
                    # Read index if requested
                    if include_index:
                        try:
                            index = await kb_manager.read_index(components)
                            doc_data["index"] = index.model_dump()
                        except FileNotFoundError:
                            doc_data["index_error"] = "Index not found"
                        except Exception as e:
                            doc_data["index_error"] = str(e)
                    
                    # Read content if requested
                    if include_content:
                        try:
                            content = await kb_manager.read_content(components)
                            doc_data["content"] = content
                        except FileNotFoundError:
                            doc_data["content_error"] = "Content not found"
                        except Exception as e:
                            doc_data["content_error"] = str(e)
                    
                    processed_docs.append(doc_data)
                except Exception as e:
                    # If we can't parse the path, include it with an error
                    processed_docs.append({
                        "path": doc_path,
                        "error": f"Failed to parse path: {str(e)}"
                    })
            
            return {
                "documents": processed_docs, 
                "count": len(processed_docs), 
                "mode": "bulk_read",
                "include_content": include_content,
                "include_index": include_index
            }
        
        try:
            # If no path provided, list all documents
            if not path:
                documents = await kb_manager.list_documents(recursive=recursive)
                return await _process_document_list(documents, include_content, include_index)
            
            # Parse the path to determine what we're dealing with
            try:
                # Try to parse as a complete document path first
                components = PathComponents.parse_path(path)
                
                # Check if this document actually exists
                if await kb_manager.check_index(components):
                    # This is a specific document - read it
                    if not include_content and not include_index:
                        # Default to including both if neither specified for document reading
                        include_content = True
                        include_index = True
                    
                    result = {
                        "status": "success",
                        "path": path,
                        "mode": "read"
                    }
                    
                    # Read index if requested
                    if include_index:
                        try:
                            index = await kb_manager.read_index(components)
                            result["index"] = index.model_dump()
                        except FileNotFoundError as e:
                            return {
                                "status": "error",
                                "error": f"Document index not found: {str(e)}"
                            }
                    
                    # Read content if requested
                    if include_content:
                        try:
                            content = await kb_manager.read_content(components)
                            result["content"] = content
                        except FileNotFoundError as e:
                            # If index was successfully read but content is missing,
                            # return partial success with a warning
                            if include_index and "index" in result:
                                result["content"] = None
                                result["content_warning"] = f"Content not found: {str(e)}"
                            else:
                                return {
                                    "status": "error",
                                    "error": f"Document content not found: {str(e)}"
                                }
                    
                    return result
                else:
                    # Document doesn't exist, treat as partial path for listing
                    partial_components = PartialPathComponents.parse_path(path)
                    documents = await kb_manager.list_documents(
                        components=partial_components,
                        recursive=recursive
                    )
                    return await _process_document_list(documents, include_content, include_index)
                    
            except ValueError:
                # Path couldn't be parsed as complete document path, treat as partial
                partial_components = PartialPathComponents.parse_path(path)
                documents = await kb_manager.list_documents(
                    components=partial_components,
                    recursive=recursive
                )
                return await _process_document_list(documents, include_content, include_index)
                
        except ValueError as e:
            return {
                "status": "error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error in kb_read: {e}", exc_info=True, stack_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
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
    async def kb_update_triples(action: str,
                                triple_type: str,
                                path: str,
                                predicate: str,
                                object: Optional[str] = None,
                                ref_path: Optional[str] = None) -> Dict[str, Any]:
        """Manage RDF triples (preferences, references, and metadata) for documents.
        
        Args:
            action: Action to perform ("add" or "remove")
            triple_type: Type of triple ("preference", "reference", or "metadata")
            path: Source document path
            predicate: Predicate of the triple
            object: Object of the triple (for preferences) or relation name (for references) or metadata value (for metadata)
            ref_path: Referenced document path (for references only)
            
        Returns:
            Dictionary with status and operation results
        """
        try:
            # Validate action
            if action not in ["add", "remove"]:
                return {
                    "action": action,
                    "triple_type": triple_type,
                    "status": "error",
                    "error": f"Invalid action: {action}. Must be 'add' or 'remove'"
                }
            
            # Validate triple_type
            if triple_type not in ["preference", "reference", "metadata"]:
                return {
                    "action": action,
                    "triple_type": triple_type,
                    "status": "error",
                    "error": f"Invalid triple_type: {triple_type}. Must be 'preference', 'reference', or 'metadata'"
                }
            
            # Parse the source path
            components = PathComponents.parse_path(path)
            
            # Handle preferences
            if triple_type == "preference":
                if object is None:
                    return {
                        "action": action,
                        "triple_type": triple_type,
                        "status": "error",
                        "error": "object parameter is required for preference triples"
                    }
                
                # Create preference triple
                preferences = [ImplicitRDFTriple(predicate=predicate, object=object)]
                
                if action == "add":
                    result = await kb_manager.add_preference(
                        components=components,
                        preferences=preferences
                    )
                else:  # remove
                    result = await kb_manager.remove_preference(
                        components=components,
                        preferences=preferences
                    )
            
            # Handle references
            elif triple_type == "reference":
                if ref_path is None:
                    return {
                        "action": action,
                        "triple_type": triple_type,
                        "status": "error",
                        "error": "ref_path parameter is required for reference triples"
                    }
                
                # Parse the referenced path
                ref_components = PathComponents.parse_path(ref_path)
                
                # Use predicate as the relation name for references
                relation = predicate
                
                if action == "add":
                    result = await kb_manager.add_reference(
                        components=components,
                        ref_components=ref_components,
                        relation=relation
                    )
                else:  # remove
                    result = await kb_manager.remove_reference(
                        components=components,
                        ref_components=ref_components,
                        relation=relation
                    )
            
            # Handle metadata
            elif triple_type == "metadata":
                if action == "add":
                    if object is None:
                        return {
                            "action": action,
                            "triple_type": triple_type,
                            "status": "error",
                            "error": "object parameter is required for metadata add operations"
                        }
                    
                    # Add metadata property using predicate as key and object as value
                    result = await kb_manager.add_metadata_property(
                        components=components,
                        key=predicate,
                        value=object
                    )
                else:  # remove
                    # Remove metadata property using predicate as key
                    result = await kb_manager.remove_metadata_property(
                        components=components,
                        key=predicate
                    )
            
            # Add action and triple_type to result for context
            result.update({
                "action": action,
                "triple_type": triple_type
            })
            
            return result
            
        except ValueError as e:
            return {
                "action": action,
                "triple_type": triple_type,
                "status": "error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error managing {triple_type} {action}: {e}", exc_info=True, stack_info=True)
            return {
                "action": action,
                "triple_type": triple_type,
                "status": "error",
                "error": str(e)
            }

    @mcp.tool()
    async def kb_update_metadata(path: str,
                               metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Update metadata for a document in the knowledge base.
        
        DEPRECATED: Use kb_update_triples with triple_type="metadata" instead.
        This function updates the entire metadata dictionary. For individual
        key-value operations, use kb_update_triples with:
        - action="add", triple_type="metadata", predicate=key, object=value
        - action="remove", triple_type="metadata", predicate=key
        
        Args:
            path: Document path in format "namespace/collection[/subcollection]*/name"
            metadata: Document metadata dictionary (replaces entire metadata)
            
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
            
            result = index.model_dump()
            result.update({
                "status": "success",
                "warning": "kb_update_metadata is deprecated. Use kb_update_triples with triple_type='metadata' for individual key-value operations."
            })
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
            logger.error(f"Error updating metadata for {path}: {e}", exc_info=True, stack_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    


    @mcp.tool()
    async def kb_manage(action: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Manage knowledge base operations like rebuilding search indices and moving documents.
        
        Args:
            action: Management action to perform. Supported actions:
                   - "rebuild_search_index": Rebuild search indices from scratch
                     optional parameters: rebuild_all (bool, default: True)
                   - "move_document": Move a document to a new location
                     required parameters: path (str, required), new_path (str, required)
                   - "delete": Archive a document
                     required parameters: path (str, required)
            options: Additional parameters for the specific action

            Example:
            {
                "action": "rebuild_search_index",
                "options": {
                    "rebuild_all": True
                }
            }
            
        Returns:
            Dictionary with operation status and results
        """
        try:
            if action == "rebuild_search_index":
                rebuild_all = options.get("rebuild_all", True)
                result = await kb_manager.recover_search_indices(rebuild_all=rebuild_all)
                return {
                    "action": action,
                    "status": "success",
                    "result": result
                }
            
            elif action == "move_document":
                # Validate required parameters
                path = options.get("path")
                new_path = options.get("new_path")
                
                if not path:
                    return {
                        "action": action,
                        "status": "error",
                        "error": "path parameter is required for move_document action"
                    }
                
                if not new_path:
                    return {
                        "action": action,
                        "status": "error",
                        "error": "new_path parameter is required for move_document action"
                    }
                
                # Parse both paths
                old_components = PathComponents.parse_path(path)
                new_components = PathComponents.parse_path(new_path)
                
                # Move document using components
                index = await kb_manager.move_document(
                    components=old_components,
                    new_components=new_components
                )
                
                return {
                    "action": action,
                    "status": "success",
                    "old_path": path,
                    "new_path": new_path,
                    "result": index.model_dump()
                }
            
            elif action == "delete":
                # Validate required parameters
                path = options.get("path")
                
                if not path:
                    return {
                        "action": action,
                        "status": "error",
                        "error": "path parameter is required for delete action"
                    }
                
                # Parse the path
                components = PathComponents.parse_path(path)
                
                # Archive document (removes from indices and moves to archive)
                result = await kb_manager.archive_document(components)
                
                return {
                    "action": action,
                    "status": "success",
                    "path": path,
                    "result": result
                }
            
            else:
                return {
                    "action": action,
                    "status": "error", 
                    "error": f"Unknown action: {action}. Supported actions: rebuild_search_index, move_document, delete"
                }
        except ValueError as e:
            return {
                "action": action,
                "status": "error", 
                "error": str(e)
            }
        except RuntimeError as e:
            return {
                "action": action,
                "status": "error", 
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error during kb_manage action '{action}': {e}", exc_info=True)
            return {
                "action": action,
                "status": "error", 
                "error": f"An unexpected error occurred: {str(e)}"
            }