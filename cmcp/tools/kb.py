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

    # Register knowledge base document resource handler
    @mcp.resource("kb://{uri}")
    async def get_kb_document(uri: str) -> str:
        """Get knowledge base document contents as a resource.
        
        Args:
            uri: Document URI
            
        Returns:
            Document content as string
        """
        try:
            # Parse the path
            components = PathComponents.parse_path(f"kb://{uri}")
            
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
                      seed_uris: Optional[List[str]] = None,
                      root_uri: Optional[str] = None,
                      expand_hops: int = 0,
                      filter_uris: Optional[List[str]] = None,
                      relation_predicates: Optional[List[str]] = None,
                      top_k_sparse: int = 50,
                      top_k_rerank: int = 10,
                      include_content: bool = False,
                      include_index: bool = False,
                      use_reranker: bool = True) -> Dict[str, Any]:
        """Search the knowledge base using text queries and graph relationships.

        This tool searches through documents in the knowledge base using both text matching
        and graph relationship traversal. You can search by content, follow document references,
        or combine both approaches for comprehensive knowledge discovery.
        
        Args:
            query: Text query to search for
             or
            seed_uris: Starting URIs for graph expansion (full kb://namespace/collection/name uri)
             or
            root_uri: Root URI to start search from (partial kb://namespace <optional>/collection <optional> uri)
            
            expand_hops: Number of relationship hops to expand
            filter_uris: URIs to filter out from search
            relation_predicates: RDF predicates to use for graph expansion
            top_k_sparse: Number of top sparse results to return
            top_k_rerank: Number of top reranked results to return
            include_content: Whether to include document content in results
            include_index: Whether to include document index in results
            use_reranker: Whether to use reranker to score results

        Examples:
        
        Request: {"name": "kb_search", "parameters": {"query": "machine learning algorithms", "top_k_rerank": 5}}
        Response: {"results": [{"uri": "kb://ai/ml/algorithms", "score": 0.95, "title": "ML Algorithms Overview"}], "count": 5}

        To search a branch of the knowledge base and getting the index:
        Request: {"name": "kb_search", "parameters": {"root_uri": "kb://", "include_index": true}}

        To search a specific document with graph expansion, returning the content:
        Request: {"name": "kb_search", "parameters": {"seed_uris": ["kb://project/docs/main"], "expand_hops": 2, "include_content": true}}
        """
        try:
            if root_uri is not None:
                partial_components = PartialPathComponents.parse_path(root_uri)
                logger.info(f"Searching branch of the knowledge base: {partial_components}")
                results = await kb_manager.list_documents(
                    components=partial_components,
                    recursive=True,
                    filter_uris=filter_uris,
                    include_index=include_index,
                    include_content=include_content
                )
                return {"results": results, "count": len(results)}
            
            if query is None and seed_uris is None:
                return {"status": "error", "error": "Either query or seed_uris or root_uri must be provided"}
            
            results = await kb_manager.search(
                query=query,
                seed_uris=seed_uris,
                expand_hops=expand_hops,
                filter_uris=filter_uris,
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
    async def kb_read(uri: Optional[str] = None,
                     recursive: bool = True,
                     include_content: bool = False,
                     include_index: bool = False) -> Dict[str, Any]:
        """Read documents or browse collections in the knowledge base.
        
        This tool can list all documents in the knowledge base, browse specific collections,
        or read individual documents with their content and metadata. Use without a path 
        to see all available documents, or provide a specific document path to read it.
        
        Examples:
        
        Request: {"name": "kb_read", "parameters": {}}
        Response: {"documents": ["kb://notes/meeting-2024-01", "kb://docs/api-spec"], "count": 2, "mode": "list"}
        
        Request: {"name": "kb_read", "parameters": {"uri": "kb://notes/meeting-2024-01", "include_content": true, "include_index": true}}
        Response: {"status": "success", "uri": "kb://notes/meeting-2024-01", "content": "Meeting notes...", "index": {"title": "Team Meeting", "created": "2024-01-01"}}
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
                    doc_data = {"uri": components.uri}
                    
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
            if not uri:
                documents = await kb_manager.list_documents(recursive=recursive)
                return await _process_document_list(documents, include_content, include_index)
            
            # Parse the path to determine what we're dealing with
            try:
                # Try to parse as a complete document path first
                components = PathComponents.parse_path(uri)
                
                # Check if this document actually exists
                if await kb_manager.check_index(components):
                    # This is a specific document - read it
                    if not include_content and not include_index:
                        # Default to including both if neither specified for document reading
                        include_content = True
                        include_index = True
                    
                    result = {
                        "status": "success",
                        "uri": uri,
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
                    partial_components = PartialPathComponents.parse_path(uri)
                    documents = await kb_manager.list_documents(
                        components=partial_components,
                        recursive=recursive
                    )
                    return await _process_document_list(documents, include_content, include_index)
                    
            except ValueError:
                # Path couldn't be parsed as complete document path, treat as partial
                partial_components = PartialPathComponents.parse_path(uri)
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
    async def kb_create_document(uri: str,
                              metadata: Optional[Dict[str, Any]] = None,
                              content: Optional[str] = None) -> Dict[str, Any]:
        """Create a new document structure in the knowledge base with metadata.
        
        This tool creates the document structure and index with metadata but no content yet.
        After creating the document, use kb_write_content to add the actual content.
        This two-step approach ensures the document path is valid before adding content.
        
        Examples:
        
        Request: {"name": "kb_create_document", "parameters": {"uri": "kb://project/docs/api-guide", "metadata": {"title": "API Guide", "author": "dev-team"}}}
        Response: {"urn": "kb://project/docs/api-guide", "title": "API Guide", "author": "dev-team", "created": "2024-01-01T10:00:00Z"}
        
        Request: {"name": "kb_create_document", "parameters": {"uri": "kb://notes/weekly-standup-2024-01-15"}}
        Response: {"urn": "kb://notes/weekly-standup-2024-01-15", "created": "2024-01-15T10:00:00Z", "title": "weekly-standup-2024-01-15"}
        """
        try:
            # Parse the path to get components
            components = PathComponents.parse_path(uri)
            
            # Use default empty metadata if not provided
            if metadata is None:
                metadata = {}
            
            # Create document with metadata only
            index = await kb_manager.create_document(
                components=components,
                metadata=metadata
            )

            if content:
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
        except Exception as e:
            logger.error(f"Error creating document at {uri}: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    @mcp.tool()
    async def kb_write_content(uri: str,
                             content: str,
                             force: bool = False) -> Dict[str, Any]:
        """Add content to an existing document in the knowledge base.
        
        This tool writes the actual content to a document that was previously created with
        kb_create_document. The document structure must already exist before adding content.
        Use force=true to overwrite existing content if needed.
        
        Examples:
        
        Request: {"name": "kb_write_content", "parameters": {"uri": "kb://project/docs/api-guide", "content": "# API Guide\\n\\nThis guide covers..."}}
        Response: {"urn": "kb://project/docs/api-guide", "content_size": 1024, "updated": "2024-01-01T10:30:00Z"}
        
        Request: {"name": "kb_write_content", "parameters": {"uri": "kb://notes/meeting-notes", "content": "Updated meeting notes...", "force": true}}
        Response: {"urn": "kb://notes/meeting-notes", "content_size": 512, "updated": "2024-01-01T11:00:00Z", "overwritten": true}
        """
        try:
            # Parse the path to get components
            components = PathComponents.parse_path(uri)
            
            # Check if document exists (index must exist)
            if not await kb_manager.check_index(components):
                return {
                    "status": "error",
                    "error": f"Document not found: {uri}. Create it first using kb_create_document."
                }
            
            # Check if content already exists using the check_content method
            if await kb_manager.check_content(components) and not force:
                return {
                    "status": "error",
                    "error": f"Content already exists at path: {components.uri}. Use force=True to overwrite existing content."
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
            logger.error(f"Error writing content to {uri}: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    


    @mcp.tool()
    async def kb_update_triples(action: str,
                                triple_type: str,
                                uri: str,
                                predicate: str,
                                object: Optional[str] = None,
                                ref_uri: Optional[str] = None) -> Dict[str, Any]:
        """Manage relationships and metadata between documents in the knowledge base.
        
        This tool adds or removes semantic relationships (references), preferences, 
        and metadata properties for documents. Use it to create connections between 
        related documents or add structured metadata.
        
        Examples:
        
        Request: {"name": "kb_update_triples", "parameters": {"action": "add", "triple_type": "reference", "uri": "kb://docs/api", "predicate": "references", "ref_uri": "kb://examples/code-samples"}}
        Response: {"action": "add", "triple_type": "reference", "status": "success", "relations_count": 3}
        
        Request: {"name": "kb_update_triples", "parameters": {"action": "add", "triple_type": "metadata", "uri": "kb://docs/guide", "predicate": "priority", "object": "high"}}
        Response: {"action": "add", "triple_type": "metadata", "status": "success", "metadata_updated": {"priority": "high"}}
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
            components = PathComponents.parse_path(uri)
            
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
                if ref_uri is None:
                    return {
                        "action": action,
                        "triple_type": triple_type,
                        "status": "error",
                        "error": "ref_path parameter is required for reference triples"
                    }
                
                # Parse the referenced path
                ref_components = PathComponents.parse_path(ref_uri)
                
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
    async def kb_manage(action: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Perform administrative operations on the knowledge base.
        
        This tool handles maintenance tasks like rebuilding search indices, moving documents
        to new locations, and archiving documents. Use for knowledge base administration
        and organization tasks.
        
        Examples:
        
        Request: {"name": "kb_manage", "parameters": {"action": "rebuild_search_index", "options": {"rebuild_all": true}}}
        Response: {"action": "rebuild_search_index", "status": "success", "result": {"documents_indexed": 150, "time_taken": "2.3s"}}
        
        Request: {"name": "kb_manage", "parameters": {"action": "move_document", "options": {"uri": "kb://temp/draft", "new_uri": "kb://docs/final-spec"}}}
        Response: {"action": "move_document", "status": "success", "old_uri": "kb://temp/draft", "new_uri": "kb://docs/final-spec"}
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
                uri = options.get("uri")
                new_uri = options.get("new_uri")
                
                if not uri:
                    return {
                        "action": action,
                        "status": "error",
                        "error": "uri parameter is required for move_document action"
                    }
                
                if not new_uri:
                    return {
                        "action": action,
                        "status": "error",
                        "error": "new_uri parameter is required for move_document action"
                    }
                
                # Parse both paths
                old_components = PathComponents.parse_path(uri)
                new_components = PathComponents.parse_path(new_uri)
                
                # Move document using components
                index = await kb_manager.move_document(
                    components=old_components,
                    new_components=new_components
                )
                
                return {
                    "action": action,
                    "status": "success",
                    "old_uri": uri,
                    "new_uri": new_uri,
                    "result": index.model_dump()
                }
            
            elif action == "delete":
                # Validate required parameters
                uri = options.get("uri")
                
                if not uri:
                    return {
                        "action": action,
                        "status": "error",
                        "error": "uri parameter is required for delete action"
                    }
                
                # Parse the path
                components = PathComponents.parse_path(uri)
                
                # Archive document (removes from indices and moves to archive)
                result = await kb_manager.archive_document(components)
                
                return {
                    "action": action,
                    "status": "success",
                    "uri": uri,
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