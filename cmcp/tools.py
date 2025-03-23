"""MCP tools module.

This module contains factory functions that create MCP tools for different functionalities.
Each factory takes managers as input and returns a configured tool function.
"""

from typing import Dict, Any, Optional, List, Tuple, Callable
import logging

logger = logging.getLogger(__name__)


def create_system_tools(mcp, bash_manager, python_manager):
    """Create and register system tools.
    
    Args:
        mcp: The MCP instance
        bash_manager: The bash manager instance
        python_manager: The python manager instance
    """
    import os
    
    @mcp.tool()
    async def system_run_command(command: str, working_dir: Optional[str] = None) -> Dict[str, Any]:
        """Execute a bash command safely in a sandboxed environment.

        See AVAILABLE_COMMANDS.txt for the extensive list of allowed commands.
        
        Args:
            command: The bash command to execute
            working_dir: Optional working directory (ignored in sandbox)
            
        Returns:
            Dictionary containing stdout, stderr, and exit code
        """
        result = await bash_manager.execute(command)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code
        }
    
    @mcp.tool()
    async def system_run_python(code: str, working_dir: Optional[str] = None) -> Dict[str, Any]:
        """Execute Python code in a secure sandbox.
        
        Args:
            code: Python code to execute
            working_dir: Optional working directory (ignored in sandbox)
            
        Returns:
            Dictionary containing output, error, and execution result
        """
        result = await python_manager.execute(code)
        return {
            "output": result.output,
            "error": result.error,
            "result": result.result
        }
    
    @mcp.tool()
    async def system_env_var(var_name: Optional[str] = None) -> Dict[str, Any]:
        """Get environment variable values.
        
        Args:
            var_name: Specific environment variable to get (optional)
            
        Returns:
            Dictionary containing environment variables
        """
        if var_name:
            return {
                "variables": {var_name: os.environ.get(var_name, "")},
                "requested_var": os.environ.get(var_name, "")
            }
        else:
            # Only return safe environment variables
            safe_env = {}
            for key, value in os.environ.items():
                # Filter out sensitive variables
                if not any(sensitive in key.lower() for sensitive in ["key", "secret", "password", "token", "auth"]):
                    safe_env[key] = value
            return {"variables": safe_env}


def create_file_tools(mcp, file_manager):
    """Create and register file tools.
    
    Args:
        mcp: The MCP instance
        file_manager: The file manager instance
    """
    @mcp.tool()
    async def file_read(path: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """Read file contents safely.
        
        Args:
            path: Path to the file (relative to sandbox root)
            encoding: File encoding
            
        Returns:
            Dictionary containing file content and metadata
        """
        try:
            content, metadata = await file_manager.read_file(path)
            return {
                "content": content,
                "size": metadata.size,
                "modified": metadata.modified_time,
                "success": True
            }
        except Exception as e:
            logger.warning(f"Error reading file {path}: {str(e)}")
            return {
                "content": "",
                "error": str(e),
                "success": False
            }
    
    @mcp.tool()
    async def file_write(path: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """Write content to a file safely.
        
        Args:
            path: Path to the file (relative to sandbox root)
            content: Content to write
            encoding: File encoding
            
        Returns:
            Dictionary containing success status and file path
        """
        try:
            success = await file_manager.write_file(path, content)
            return {
                "success": success,
                "path": path
            }
        except Exception as e:
            logger.warning(f"Error writing file {path}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @mcp.tool()
    async def file_list(path: str = "/", pattern: Optional[str] = None, recursive: bool = True) -> Dict[str, Any]:
        """List contents of a directory safely.
        
        Args:
            path: Path to the directory (relative to sandbox root)
            pattern: Optional glob pattern to filter files
            recursive: Whether to list files recursively (default: True)
            
        Returns:
            Dictionary containing directory entries
        """
        try:
            entries = await file_manager.list_directory(path, recursive=recursive)
            
            # Apply pattern filtering if specified
            if pattern:
                import fnmatch
                entries = [entry for entry in entries if fnmatch.fnmatch(entry["name"], pattern)]
                
            return {
                "entries": entries,
                "path": path,
                "success": True
            }
        except Exception as e:
            logger.warning(f"Error listing directory {path}: {str(e)}")
            return {
                "entries": [],
                "path": path,
                "error": str(e),
                "success": False
            }
    
    @mcp.tool()
    async def file_delete(path: str) -> Dict[str, Any]:
        """Delete a file safely.
        
        Args:
            path: Path of the file to delete
            
        Returns:
            Dictionary containing success status and path
        """
        try:
            success = await file_manager.delete_file(path)
            return {
                "success": success,
                "path": path
            }
        except Exception as e:
            logger.warning(f"Error deleting file {path}: {str(e)}")
            return {
                "success": False,
                "path": path,
                "error": str(e)
            }
    
    @mcp.tool()
    async def file_move(source: str, destination: str) -> Dict[str, Any]:
        """Move or rename a file safely.
        
        Args:
            source: Source file path
            destination: Destination file path
            
        Returns:
            Dictionary containing success status, source and destination
        """
        try:
            success = await file_manager.move_file(source, destination)
            return {
                "success": success,
                "source": source,
                "destination": destination
            }
        except Exception as e:
            logger.warning(f"Error moving file {source} to {destination}: {str(e)}")
            return {
                "success": False,
                "source": source,
                "destination": destination,
                "error": str(e)
            }
    
    # Register file resource handler
    @mcp.resource("file://{path}")
    async def get_file(path: str) -> str:
        """Get file contents as a resource.
        
        Args:
            path: Path to the file (relative to sandbox root)
            
        Returns:
            File contents
        """
        try:
            content, _ = await file_manager.read_file(path)
            return content
        except Exception as e:
            logger.error(f"Error accessing file resource {path}: {str(e)}")
            return f"Error: {str(e)}"


def create_web_tools(mcp, web_manager):
    """Create and register web tools.
    
    Args:
        mcp: The MCP instance
        web_manager: The web manager instance
    """
    @mcp.tool()
    async def web_search(query: str) -> Dict[str, Any]:
        """Use a search engine to find information on the web.
        
        Args:
            query: The query to search the web for
            
        Returns:
            Dictionary containing search results
        """
        return await web_manager.search_web(query)
    
    @mcp.tool()
    async def web_scrape(url: str, selector: Optional[str] = None) -> Dict[str, Any]:
        """Scrape a specific URL and return the content.
        
        Args:
            url: The URL to scrape
            selector: Optional CSS selector to target specific content
            
        Returns:
            Dictionary containing page content and metadata
        """
        result = await web_manager.scrape_webpage(url, selector)
        return {
            "content": result.content,
            "url": result.url,
            "title": result.title,
            "success": result.success,
            "error": result.error
        }
    
    @mcp.tool()
    async def web_browse(url: str) -> Dict[str, Any]:
        """Interactively browse a website using Playwright.
        
        Args:
            url: Starting URL for browsing session
            
        Returns:
            Dictionary containing page content and metadata
        """
        result = await web_manager.browse_webpage(url)
        return {
            "content": result.content,
            "url": result.url,
            "title": result.title,
            "success": result.success,
            "error": result.error
        }


def create_kb_tools(mcp):
    """Create and register knowledge base tools.
    
    Args:
        mcp: The MCP instance
    """
    from cmcp.managers.knowledge_base_manager import KnowledgeBaseManager
    
    @mcp.tool()
    async def kb_write_document(content: str, namespace: str = None, collection: str = None, name: str = None, metadata: dict = None):
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
    async def kb_read_document(namespace: str, collection: str, name: str, chunk_num: Optional[int] = None):
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
            error_message = f"Error reading document {namespace}/{collection}/{name}: {str(e)}"
            logger.warning(error_message)
            return {
                "error": "The document was invalid. Please repair the document metadata.",
                "detail": str(e)
            }
    
    @mcp.tool()
    async def kb_add_preference(namespace: str, collection: str, name: str, subject: str, predicate: str, object: str):
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
    async def kb_remove_preference(namespace: str, collection: str, name: str, subject: str, predicate: str, object: str):
        """Remove a specific preference triple from a document.
        
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
        
        # Create a triple to remove
        triple = [(subject, predicate, object)]
        result = await kb_manager.remove_preference(document_path, triple)
        
        return result
    
    @mcp.tool()
    async def kb_remove_all_preferences(namespace: str, collection: str, name: str):
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
    async def kb_add_reference(namespace: str, collection: str, name: str, 
                             ref_namespace: str, ref_collection: str, ref_name: str, relation: str):
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
    async def kb_remove_reference(namespace: str, collection: str, name: str, 
                               ref_namespace: str, ref_collection: str, ref_name: str, relation: str):
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
    async def kb_list_documents(namespace: Optional[str] = None, collection: Optional[str] = None, recursive: bool = True):
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
    async def kb_move_document(namespace: str, collection: str, name: str, 
                             new_namespace: Optional[str] = None, 
                             new_collection: Optional[str] = None, 
                             new_name: Optional[str] = None):
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
            logger.error(f"Error accessing knowledge base document {namespace}/{collection}/{name}: {str(e)}")
            return f"Error: {str(e)}"


def register_all_tools(mcp, bash_manager, python_manager, file_manager, web_manager):
    """Register all tools with the MCP instance.
    
    Args:
        mcp: The MCP instance
        bash_manager: The bash manager instance
        python_manager: The python manager instance
        file_manager: The file manager instance
        web_manager: The web manager instance
    """
    create_system_tools(mcp, bash_manager, python_manager)
    create_file_tools(mcp, file_manager)
    create_web_tools(mcp, web_manager)
    create_kb_tools(mcp) 